# NC Bank Available Balance

Shows what a bank account will hold once everything pending has cleared.

```
Available = Balance - Unreconciled transactions + Incoming payments + Outgoing payments
```

* **Balance**: the dashboard balance, which is the bank feed's running balance plus direct payments.
* **Unreconciled transactions**: posted bank transactions that aren't reconciled yet. They are
  already in the balance, and the payment they settle still counts as outstanding until
  reconciliation, so they are backed out to avoid counting the same money twice.
* **Incoming / Outgoing payments**: payments not yet matched with a bank transaction, plus
  open Misc. journal items on an outstanding receipts/payments account that are tagged with
  this bank (e.g. payroll checks entered as a journal entry).

## Setup

On each Miscellaneous journal, set **Default Bank** (Journal Entries tab). New lines on
outstanding accounts get that bank automatically. Setting it also fills existing open lines
that have no bank yet. To change the bank of a single line, edit the **Bank** column on the
entry's Journal Items tab (draft) or in **Bank Balances** (posted).

## Where it shows

* Accounting dashboard, bank/cash cards: **Payments** includes the tagged Misc. lines, and a
  new **Available** row appears (red when negative). Both links open **Bank Balances**.
* **Accounting > Accounting > Transactions > Bank Balances**: pick a bank account, then click
  a bubble (Unreconciled / Incoming / Outgoing) to filter the list.
