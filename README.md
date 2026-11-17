# Bank Available Balance for Odoo 19

The **NC Bank Available Balance** Odoo module and how to use it: see what a checking account
will actually hold once every pending payment and bank transaction has cleared.

## Video walkthrough (1 min)

[![Watch the walkthrough](demo-poster.png)](https://nc-automation.github.io/bank-available-balance/)

Click the image to [watch the video](https://nc-automation.github.io/bank-available-balance/), or [download the MP4](https://github.com/NC-Automation/bank-available-balance/raw/main/bank-available-balance-demo.mp4). The video uses Odoo demo data.

## The problem

The Accounting dashboard shows a bank **Balance** (latest bank feed balance) and
**Payments** (outstanding payments), but nothing tells you what is really available:

- Unreconciled bank transactions are already in the balance, yet the payments they settle
  still count as outstanding, so subtracting Payments from Balance counts them twice.
- Checks entered as journal entries in a Miscellaneous journal (payroll, for example) don't
  count as Payments at all.

## What the module adds

```
Available = Balance − Unreconciled transactions + Incoming payments + Outgoing payments
```

- **Default Bank on Miscellaneous journals.** Journal items posted on an Outstanding
  Receipts/Payments account get a **Bank** field, filled in from the journal's Default Bank.
- **Payments include Misc. entries.** The dashboard Payments amount adds open Misc. items
  tagged with that bank.
- **Available on the dashboard.** A new row under Payments, in red when negative.
- **Bank Balances view.** Opened by clicking Available or Payments, or from
  *Accounting ▸ Transactions ▸ Bank Balances*. Pick the bank account at the top, then click
  the bubbles to filter the list:
  - Unreconciled Transactions
  - Incoming Payments
  - Outgoing Payments

  Click Balance or Available to show everything again.

## Installation

Requires **Odoo 19** (Community or Enterprise). It depends only on the standard
`account` module.

The module is the [`nc_bank_available_balance`](nc_bank_available_balance) folder in this
repository.

### Self-hosted Odoo

1. Copy the module folder into one of your addons directories:

   ```bash
   git clone https://github.com/NC-Automation/bank-available-balance.git
   cp -r bank-available-balance/nc_bank_available_balance /path/to/your/addons/
   ```

   Or add the cloned repository folder itself to `addons_path` in your Odoo config.
2. Restart Odoo.
3. Turn on developer mode (*Settings ▸ Activate the developer mode*).
4. Go to *Apps ▸ Update Apps List*.
5. Search for **Bank Available Balance** (remove the *Apps* filter) and click **Activate**.

### Odoo.sh

1. Add this repository as a submodule of your Odoo.sh repository:

   ```bash
   git submodule add -b main https://github.com/NC-Automation/bank-available-balance.git bank-available-balance
   git commit -m "Add Bank Available Balance module"
   git push
   ```

   Odoo.sh adds submodule folders to the addons path automatically.
2. When the build is done, install **Bank Available Balance** from *Apps* as above.

### Odoo Online (SaaS)

Odoo Online doesn't allow custom Python modules. You need Odoo.sh or a self-hosted Odoo.

## Setup

1. Install the module (see above).
2. Open *Accounting ▸ Configuration ▸ Journals ▸ Miscellaneous Operations* and set
   **Default Bank** on the *Journal Entries* tab. Existing open items without a bank get it too.
3. To change the bank on a single item, use the **Bank** column on the entry's Journal Items
   tab (draft entries) or in Bank Balances (posted entries).

The Default Bank field and Journal Items tab need *Show Full Accounting Features* turned on
for the user.

## License

[LGPL-3](LICENSE)
