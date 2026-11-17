from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestAvailableBalance(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank = cls.company_data["default_journal_bank"]
        cls.misc = cls.company_data["default_journal_misc"]
        cls.misc.nc_default_bank_journal_id = cls.bank
        cls.outstanding_payments = cls.bank.outbound_payment_method_line_ids.payment_account_id[:1]
        cls.expense = cls.company_data["default_account_expense"]

    def _misc_entry(self, amount, post=True):
        move = self.env["account.move"].create({
            "move_type": "entry",
            "journal_id": self.misc.id,
            "line_ids": [
                Command.create({"account_id": self.expense.id, "debit": amount}),
                Command.create({"account_id": self.outstanding_payments.id, "credit": amount}),
            ],
        })
        if post:
            move.action_post()
        return move

    def _summary(self):
        return self.bank._nc_available_summary()[self.bank.id]

    def test_misc_line_gets_default_bank(self):
        move = self._misc_entry(200.0, post=False)
        outstanding_line = move.line_ids.filtered(lambda l: l.account_id == self.outstanding_payments)
        expense_line = move.line_ids - outstanding_line
        self.assertEqual(outstanding_line.nc_bank_journal_id, self.bank)
        self.assertTrue(outstanding_line.nc_is_outstanding_line)
        self.assertFalse(expense_line.nc_bank_journal_id)

    def test_available_balance(self):
        self.assertTrue(self.outstanding_payments, "test needs an outstanding payments account")
        # Bank feed: +1000 deposit (reconciled-ish: stays unreconciled here) and a -30 transaction.
        st_lines = self.env["account.bank.statement.line"].create([
            {"journal_id": self.bank.id, "date": "2026-01-01", "payment_ref": "deposit", "amount": 1000.0},
            {"journal_id": self.bank.id, "date": "2026-01-02", "payment_ref": "check 1", "amount": -30.0},
        ])
        before = self._summary()
        self.assertEqual(before["balance"], 970.0)
        self.assertEqual(before["unreconciled"], 970.0)
        self.assertEqual(before["unreconciled_count"], 2)

        payment = self.env["account.payment"].create({
            "payment_type": "outbound",
            "partner_type": "supplier",
            "partner_id": self.partner_a.id,
            "amount": 100.0,
            "journal_id": self.bank.id,
        })
        payment.action_post()
        incoming = self.env["account.payment"].create({
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.partner_a.id,
            "amount": 40.0,
            "journal_id": self.bank.id,
        })
        incoming.action_post()
        self._misc_entry(200.0)

        summary = self._summary()
        self.assertEqual(summary["incoming"], 40.0)
        self.assertEqual(summary["incoming_count"], 1)
        self.assertEqual(summary["outgoing"], -300.0)
        self.assertEqual(summary["outgoing_count"], 2)
        # 970 - 970 + 40 - 300
        self.assertEqual(summary["available"], -260.0)

        # Dashboard "Payments" includes the misc line.
        count, amount = self.bank._get_journal_dashboard_outstanding_payments()[self.bank.id]
        self.assertTrue(count)  # Odoo counts currency groups here; only used as a "has any" flag
        self.assertEqual(amount, -260.0)
        dashboard = self.bank._get_journal_dashboard_data_batched()[self.bank.id]
        self.assertTrue(dashboard["nc_show_available"])
        self.assertTrue(dashboard["nc_available_negative"])

        # Bank Balances view filters.
        Line = self.env["account.move.line"]
        self.assertEqual(len(Line.search([("nc_balance_journal_id", "=", self.bank.id)])), 5)
        self.assertEqual(len(Line.search([("nc_balance_category", "=", "outgoing")])), 2)
        unreconciled = Line.search([("nc_balance_category", "=", "unreconciled")])
        self.assertEqual(unreconciled.statement_line_id, st_lines)
        self.assertEqual(sorted(unreconciled.mapped("nc_open_amount")), [-30.0, 1000.0])

    def test_setting_default_bank_fills_existing_lines(self):
        self.misc.nc_default_bank_journal_id = False
        move = self._misc_entry(75.0)
        line = move.line_ids.filtered(lambda l: l.account_id == self.outstanding_payments)
        self.assertFalse(line.nc_bank_journal_id)
        self.misc.nc_default_bank_journal_id = self.bank
        self.assertEqual(line.nc_bank_journal_id, self.bank)
        self.assertEqual(line.nc_balance_category, "outgoing")
        self.assertEqual(line.nc_open_amount, -75.0)
