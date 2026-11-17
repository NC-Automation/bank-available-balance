from odoo import api, fields, models

from .account_journal import LIQUIDITY_TYPES

BALANCE_CATEGORIES = [
    ("unreconciled", "Unreconciled Transaction"),
    ("incoming", "Incoming Payment"),
    ("outgoing", "Outgoing Payment"),
]


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    # Set by the user (defaulted from the misc journal's Default Bank) on misc. journal
    # items posted on an outstanding receipts/payments account.
    nc_bank_journal_id = fields.Many2one(
        "account.journal",
        string="Bank",
        compute="_compute_nc_bank_journal_id",
        store=True,
        readonly=False,
        precompute=True,
        index="btree_not_null",
        check_company=True,
        domain="[('type', 'in', ('bank', 'cash', 'credit'))]",
        help="Bank this outstanding item will clear through. Open items count as "
             "outstanding payments of that bank on the dashboard.",
    )
    nc_is_outstanding_line = fields.Boolean(compute="_compute_nc_is_outstanding_line")

    # Bank Balances view (computed from account.journal._nc_balance_items).
    nc_balance_journal_id = fields.Many2one(
        "account.journal",
        string="Bank Account",
        compute="_compute_nc_balance_fields",
        search="_search_nc_balance_journal_id",
    )
    nc_balance_category = fields.Selection(
        BALANCE_CATEGORIES,
        string="Open Item Type",
        compute="_compute_nc_balance_fields",
        search="_search_nc_balance_category",
    )
    nc_balance_source = fields.Selection(
        [("statement", "Bank Transaction"), ("payment", "Payment"), ("misc", "Misc. Entry")],
        string="Source",
        compute="_compute_nc_balance_fields",
    )
    nc_balance_currency_id = fields.Many2one("res.currency", compute="_compute_nc_balance_fields")
    nc_open_amount = fields.Monetary(
        string="Open Amount",
        currency_field="nc_balance_currency_id",
        compute="_compute_nc_balance_fields",
    )

    # -------------------------------------------------------------------------
    # Bank on misc. outstanding lines
    # -------------------------------------------------------------------------

    @api.model
    def _nc_outstanding_accounts(self):
        """Outstanding receipts/payments accounts used by liquidity journals."""
        return self.env["account.payment.method.line"].sudo().search([
            ("journal_id.type", "in", LIQUIDITY_TYPES),
            ("payment_account_id", "!=", False),
        ]).payment_account_id.sudo(False)

    @api.depends("account_id", "journal_id")
    def _compute_nc_is_outstanding_line(self):
        outstanding = self._nc_outstanding_accounts()
        for line in self:
            line.nc_is_outstanding_line = (
                line.journal_id.type == "general" and line.account_id in outstanding
            )

    @api.depends("account_id", "journal_id")
    def _compute_nc_bank_journal_id(self):
        general = self.filtered(lambda l: l.journal_id.type == "general")
        (self - general).nc_bank_journal_id = False
        if not general:
            return
        outstanding = self._nc_outstanding_accounts()
        for line in general:
            if line.account_id not in outstanding:
                line.nc_bank_journal_id = False
            elif not line.nc_bank_journal_id:
                line.nc_bank_journal_id = line.journal_id.nc_default_bank_journal_id

    # -------------------------------------------------------------------------
    # Bank Balances view
    # -------------------------------------------------------------------------

    def _compute_nc_balance_fields(self):
        real_ids = [line_id for line_id in self.ids if isinstance(line_id, int)]
        items = {}
        if real_ids:
            items = {
                item["line_id"]: item
                for item in self.env["account.journal"]._nc_balance_items(line_ids=real_ids)
            }
        for line in self:
            item = items.get(line.id)
            journal = self.env["account.journal"].browse(item["journal_id"]) if item else self.env["account.journal"]
            line.nc_balance_journal_id = journal
            line.nc_balance_category = item and item["category"]
            line.nc_balance_source = item and item["source"]
            line.nc_balance_currency_id = journal.currency_id or line.company_currency_id
            line.nc_open_amount = item["amount"] if item else 0.0

    def _search_nc_balance_category(self, operator, value):
        if operator not in ("in", "not in"):
            return NotImplemented
        values = set(value)
        ids = [
            item["line_id"]
            for item in self.env["account.journal"]._nc_balance_items()
            if item["category"] in values
        ]
        return [("id", operator, ids)]

    def _search_nc_balance_journal_id(self, operator, value):
        if operator in ("in", "not in"):
            journal_ids = [v for v in value if v]
        elif operator in ("ilike", "not ilike", "=like", "=ilike", "like"):
            journal_ids = self.env["account.journal"].search([("name", operator.removeprefix("not "), value)]).ids
            operator = "not in" if operator.startswith("not") else "in"
        else:
            return NotImplemented
        ids = [
            item["line_id"]
            for item in self.env["account.journal"]._nc_balance_items(journal_ids=journal_ids)
        ]
        return [("id", operator, ids)]
