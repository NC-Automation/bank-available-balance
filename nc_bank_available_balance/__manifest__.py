{
    "name": "NC Bank Available Balance",
    "version": "19.0.1.0.0",
    "summary": "Available balance on bank journals: bank balance, unreconciled "
               "transactions and outstanding payments (incl. Misc. entries)",
    "description": """
Adds an *Available* figure to bank journal cards on the Accounting dashboard and a
*Bank Balances* view explaining it:

    Available = Balance - Unreconciled transactions + Incoming payments + Outgoing payments

* Journal items on outstanding receipt/payment accounts in Miscellaneous journals get
  a *Bank* field (defaulted from the new *Default Bank* setting on the misc journal),
  so e.g. payroll checks entered as journal entries count as outstanding payments of
  that bank.
* The dashboard *Payments* amount includes those Misc. lines.
""",
    "author": "NC Automation",
    "license": "LGPL-3",
    "category": "Accounting/Accounting",
    "depends": ["account"],
    "data": [
        "views/account_journal_views.xml",
        "views/account_move_line_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "nc_bank_available_balance/static/src/**/*",
        ],
    },
    "installable": True,
}
