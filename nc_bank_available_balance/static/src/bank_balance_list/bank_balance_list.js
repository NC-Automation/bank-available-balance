import { Component, onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { listView } from "@web/views/list/list_view";
import { ListRenderer } from "@web/views/list/list_renderer";

const JOURNAL_FIELD = "nc_balance_journal_id";
const CATEGORY_FILTERS = {
    unreconciled: "nc_unreconciled",
    incoming: "nc_incoming",
    outgoing: "nc_outgoing",
};

export class BankBalanceHeader extends Component {
    static template = "nc_bank_available_balance.BankBalanceHeader";
    static props = { list: { type: Object, optional: true } };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ data: null });
        this.loadedKey = null;
        onWillStart(() => this.load());
        onWillUpdateProps((nextProps) => this.load(nextProps));
    }

    get searchModel() {
        return this.env.searchModel;
    }

    get journalSearchItem() {
        return this.searchModel.getSearchItems(
            (item) => item.type === "field" && item.fieldName === JOURNAL_FIELD
        )[0];
    }

    get selectedJournalId() {
        const item = this.journalSearchItem;
        if (!item) {
            return false;
        }
        const values = this.searchModel.query
            .filter((q) => q.searchItemId === item.id && q.autocompleteValue)
            .map((q) => q.autocompleteValue.value);
        return values.length === 1 && Number.isInteger(values[0]) ? values[0] : false;
    }

    get categoryItems() {
        const names = Object.values(CATEGORY_FILTERS);
        return this.searchModel.getSearchItems((item) => names.includes(item.name));
    }

    isCategoryActive(category) {
        const item = this.categoryItems.find((i) => i.name === CATEGORY_FILTERS[category]);
        return Boolean(item && item.isActive);
    }

    get noCategoryActive() {
        return !this.categoryItems.some((i) => i.isActive);
    }

    /**
     * Reload the totals when the selected journal or the displayed records change
     * (e.g. after the bank of a misc. line was edited).
     */
    async load(props = this.props) {
        const journalId = this.selectedJournalId;
        const records = props.list ? props.list.records : [];
        const key = JSON.stringify([
            journalId,
            records.map((r) => [r.resId, r.data.nc_bank_journal_id && r.data.nc_bank_journal_id.id]),
        ]);
        if (key === this.loadedKey) {
            return;
        }
        this.loadedKey = key;
        const data = await this.orm.call("account.journal", "nc_get_bank_balance_header", [journalId]);
        this.state.data = data;
        if (!journalId && data.journal) {
            // Opened from the menu: pick the default bank account.
            this.selectJournal(data.journal.id);
        }
    }

    selectJournal(journalId) {
        const item = this.journalSearchItem;
        const journal = this.state.data.journals.find((j) => j.id === journalId);
        if (!item || !journal) {
            return;
        }
        this.searchModel.blockNotification = true;
        this.searchModel.deactivateGroup(item.groupId);
        this.searchModel.blockNotification = false;
        this.searchModel.addAutoCompletionValues(item.id, {
            label: journal.name,
            operator: "=",
            value: journal.id,
        });
    }

    onJournalChange(ev) {
        this.selectJournal(parseInt(ev.target.value));
    }

    /**
     * Bubbles act as exclusive filters: clicking one shows only that category,
     * clicking it again (or Balance / Available) shows everything.
     */
    showCategory(category) {
        const items = this.categoryItems;
        const target = category && items.find((i) => i.name === CATEGORY_FILTERS[category]);
        const onlyTargetActive =
            target && target.isActive && items.filter((i) => i.isActive).length === 1;
        const toggles = items.filter((i) => i.isActive).map((i) => i.id);
        if (target && !onlyTargetActive) {
            toggles.push(target.id);
        }
        // Only the last toggle notifies, so the list reloads once.
        toggles.forEach((id, index) => {
            this.searchModel.blockNotification = index < toggles.length - 1;
            this.searchModel.toggleSearchItem(id);
        });
        this.searchModel.blockNotification = false;
    }
}

export class BankBalanceListRenderer extends ListRenderer {
    static template = "nc_bank_available_balance.ListRenderer";
    static components = { ...ListRenderer.components, BankBalanceHeader };
}

export const bankBalanceListView = {
    ...listView,
    Renderer: BankBalanceListRenderer,
};

registry.category("views").add("nc_bank_balance_list", bankBalanceListView);
