from collections import defaultdict

from odoo import api, fields, models
from odoo.tools import SQL

LIQUIDITY_TYPES = ("bank", "cash", "credit")
# Journal types whose dashboard card shows the "Available" amount.
AVAILABLE_TYPES = ("bank", "cash")


class AccountJournal(models.Model):
    _inherit = "account.journal"

    nc_default_bank_journal_id = fields.Many2one(
        "account.journal",
        string="Default Bank",
        check_company=True,
        domain="[('type', 'in', ('bank', 'cash', 'credit'))]",
        help="Journal items of this journal posted on an outstanding receipts/payments "
             "account get this bank by default, so they count as outstanding payments "
             "(and in the Available amount) of that bank.",
    )

    # -------------------------------------------------------------------------
    # Default bank propagation
    # -------------------------------------------------------------------------

    def write(self, vals):
        res = super().write(vals)
        if vals.get("nc_default_bank_journal_id"):
            self._nc_fill_missing_bank_on_open_lines()
        return res

    def _nc_fill_missing_bank_on_open_lines(self):
        """Give the default bank to this journal's open outstanding lines that have none yet."""
        outstanding_accounts = self.env["account.move.line"]._nc_outstanding_accounts()
        for journal in self.filtered(lambda j: j.type == "general" and j.nc_default_bank_journal_id):
            lines = self.env["account.move.line"].search([
                ("journal_id", "=", journal.id),
                ("account_id", "in", outstanding_accounts.ids),
                ("nc_bank_journal_id", "=", False),
                ("reconciled", "=", False),
                ("parent_state", "in", ("draft", "posted")),
            ])
            lines.nc_bank_journal_id = journal.nc_default_bank_journal_id

    # -------------------------------------------------------------------------
    # Open items: unreconciled transactions & outstanding payments
    # -------------------------------------------------------------------------

    @api.model
    def _nc_balance_items(self, journal_ids=None, line_ids=None):
        """All open items affecting the available balance of liquidity journals.

        Each item is a journal item (account.move.line) with:
        - ``line_id``, ``journal_id`` (the bank journal it belongs to),
        - ``source``: 'statement' (bank transaction not reconciled yet),
          'payment' (payment not matched with a bank transaction yet) or
          'misc' (open misc. journal item on an outstanding account, tagged with a bank),
        - ``category``: 'unreconciled', 'incoming' or 'outgoing',
        - ``amount``: signed, in the journal currency.
        """
        for model in ("account.move.line", "account.move", "account.bank.statement.line", "account.payment"):
            self.env[model].flush_model()

        journal_filter = SQL("AND j.id = ANY(%s)", list(journal_ids)) if journal_ids is not None else SQL()
        line_filter = SQL("WHERE items.line_id = ANY(%s)", list(line_ids)) if line_ids is not None else SQL()
        query = SQL(
            """
            WITH jr AS (
                SELECT j.id,
                       j.default_account_id,
                       (j.currency_id IS NOT NULL AND j.currency_id != c.currency_id) AS foreign_cur
                  FROM account_journal j
                  JOIN res_company c ON c.id = j.company_id
                 WHERE j.type IN %(types)s
                   AND j.company_id = ANY(%(companies)s)
                   %(journal_filter)s
            )
            SELECT items.* FROM (
                SELECT aml.id AS line_id,
                       jr.id AS journal_id,
                       'statement' AS source,
                       'unreconciled' AS category,
                       CASE WHEN jr.foreign_cur THEN aml.amount_currency ELSE aml.balance END AS amount
                  FROM account_bank_statement_line st
                  JOIN jr ON jr.id = st.journal_id
                  JOIN account_move m ON m.id = st.move_id AND m.state = 'posted'
                  JOIN account_move_line aml ON aml.move_id = m.id AND aml.account_id = jr.default_account_id
                 WHERE st.is_reconciled IS NOT TRUE

                UNION ALL

                SELECT aml.id,
                       jr.id,
                       'payment',
                       CASE WHEN p.payment_type = 'inbound' THEN 'incoming' ELSE 'outgoing' END,
                       CASE WHEN jr.foreign_cur THEN aml.amount_currency ELSE aml.balance END
                  FROM account_payment p
                  JOIN jr ON jr.id = p.journal_id
                  JOIN account_move m ON m.origin_payment_id = p.id AND m.state = 'posted'
                  JOIN account_move_line aml ON aml.move_id = m.id AND aml.account_id = p.outstanding_account_id
                 WHERE p.is_matched IS NOT TRUE

                UNION ALL

                SELECT aml.id,
                       jr.id,
                       'misc',
                       CASE WHEN (CASE WHEN jr.foreign_cur THEN aml.amount_residual_currency ELSE aml.amount_residual END) > 0
                            THEN 'incoming' ELSE 'outgoing' END,
                       CASE WHEN jr.foreign_cur THEN aml.amount_residual_currency ELSE aml.amount_residual END
                  FROM account_move_line aml
                  JOIN jr ON jr.id = aml.nc_bank_journal_id
                  JOIN account_move m ON m.id = aml.move_id
                 WHERE m.state = 'posted'
                   AND m.origin_payment_id IS NULL
                   AND m.statement_line_id IS NULL
                   AND aml.reconciled IS NOT TRUE
                   AND aml.amount_residual != 0
            ) items
            %(line_filter)s
            """,
            types=LIQUIDITY_TYPES,
            companies=self.env.companies.ids,
            journal_filter=journal_filter,
            line_filter=line_filter,
        )
        return self.env.execute_query_dict(query)

    def _nc_available_summary(self):
        """Per journal: balance, unreconciled/incoming/outgoing totals and the available amount.

        Available = Balance - Unreconciled + Incoming + Outgoing (outgoing is negative).
        Unreconciled bank transactions are already in the bank balance; until they are
        reconciled the payment they settle is still counted as outstanding, so they are
        backed out to avoid counting the same money twice.
        """
        totals = defaultdict(lambda: defaultdict(float))
        counts = defaultdict(lambda: defaultdict(int))
        for item in self._nc_balance_items(journal_ids=self.ids):
            totals[item["journal_id"]][item["category"]] += item["amount"] or 0.0
            counts[item["journal_id"]][item["category"]] += 1

        direct_payments = self._get_direct_bank_payments()
        # Odoo computes this with raw SQL and no dependencies: flush and drop any stale cache.
        self.env["account.bank.statement.line"].flush_model()
        self.env["account.bank.statement"].flush_model()
        self.invalidate_recordset(["current_statement_balance", "has_statement_lines"])
        res = {}
        for journal in self:
            currency = journal.currency_id or journal.company_id.sudo().currency_id
            balance = journal.current_statement_balance + direct_payments[journal.id][1]
            unreconciled = currency.round(totals[journal.id]["unreconciled"])
            incoming = currency.round(totals[journal.id]["incoming"])
            outgoing = currency.round(totals[journal.id]["outgoing"])
            res[journal.id] = {
                "currency": currency,
                "balance": balance,
                "unreconciled": unreconciled,
                "unreconciled_count": counts[journal.id]["unreconciled"],
                "incoming": incoming,
                "incoming_count": counts[journal.id]["incoming"],
                "outgoing": outgoing,
                "outgoing_count": counts[journal.id]["outgoing"],
                "available": currency.round(balance - unreconciled + incoming + outgoing),
            }
        return res

    # -------------------------------------------------------------------------
    # Dashboard
    # -------------------------------------------------------------------------

    def _get_journal_dashboard_outstanding_payments(self):
        """Include open misc. journal items tagged with the bank in the "Payments" amount."""
        items = self._nc_balance_items(journal_ids=self.ids)  # also flushes what super() reads in SQL
        result = super()._get_journal_dashboard_outstanding_payments()
        misc = defaultdict(lambda: [0, 0.0])
        for item in items:
            if item["source"] == "misc":
                misc[item["journal_id"]][0] += 1
                misc[item["journal_id"]][1] += item["amount"] or 0.0
        for journal_id, (count, amount) in misc.items():
            journal = self.browse(journal_id)
            currency = journal.currency_id or journal.company_id.sudo().currency_id
            base_count, base_amount = result.get(journal_id, (0, 0.0))
            result[journal_id] = (base_count + count, currency.round(base_amount + amount))
        return result

    def _fill_bank_cash_dashboard_data(self, dashboard_data):
        super()._fill_bank_cash_dashboard_data(dashboard_data)
        journals = self.filtered(lambda j: j.type in AVAILABLE_TYPES)
        if not journals:
            return
        summaries = journals._nc_available_summary()
        for journal in journals:
            summary = summaries[journal.id]
            dashboard_data[journal.id].update({
                "nc_show_available": bool(
                    dashboard_data[journal.id].get("nb_lines_bank_account_balance")
                    or summary["unreconciled_count"] or summary["incoming_count"] or summary["outgoing_count"]
                ),
                "nc_available": summary["currency"].format(summary["available"]),
                "nc_available_negative": summary["currency"].compare_amounts(summary["available"], 0) < 0,
            })

    # -------------------------------------------------------------------------
    # Bank Balances view
    # -------------------------------------------------------------------------

    def nc_action_open_bank_balances(self):
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "nc_bank_available_balance.action_bank_balances")
        context = {}
        if self:
            self.ensure_one()
            context["search_default_nc_balance_journal_id"] = self.id
        if self.env.context.get("nc_payments_only"):
            context.update(search_default_nc_incoming=1, search_default_nc_outgoing=1)
        action["context"] = context
        return action

    @api.model
    def nc_get_bank_balance_header(self, journal_id=False):
        """Data for the header of the Bank Balances list (journal selector + bubbles)."""
        journals = self.search([
            *self._check_company_domain(self.env.companies),
            ("type", "in", AVAILABLE_TYPES),
        ], order="company_id, sequence, id")
        journal = journals.filtered(lambda j: j.id == journal_id)[:1]
        if not journal:
            journal = journals.filtered(lambda j: j.company_id == self.env.company)[:1] or journals[:1]
        multi_company = len(journals.company_id) > 1
        res = {
            "journals": [{
                "id": j.id,
                "name": f"{j.name} ({j.company_id.name})" if multi_company else j.name,
            } for j in journals],
            "journal": False,
        }
        if not journal:
            return res
        summary = journal._nc_available_summary()[journal.id]
        currency = summary.pop("currency")
        res["journal"] = {"id": journal.id, "name": journal.display_name}
        res["summary"] = {
            key: {"value": value, "formatted": currency.format(value)} if not key.endswith("_count") else value
            for key, value in summary.items()
        }
        return res
