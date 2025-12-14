/** @odoo-module **/

import { registry } from "@web/core/registry";
import { X2ManyField } from "@web/views/fields/x2many/x2many_field";
import { ListRenderer } from "@web/views/list/list_renderer";
import { onMounted } from "@odoo/owl";

class SingleLineListRenderer extends ListRenderer {
    getEmptyRowIds() {
        return this.props.list.records.length ? [] : [0];
    }
}

class X2ManyFieldSingleLine extends X2ManyField {
    static template = "web.X2ManyField";
    static props = { ...X2ManyField.props };
    static components = { ...X2ManyField.components, ListRenderer: SingleLineListRenderer };
}

registry.category("fields").add("one2many_single_line", {
    component: X2ManyFieldSingleLine,
});

const originalRenderRow = ListRenderer.prototype._renderRow;
ListRenderer.prototype._renderRow = function(row, index) {
    if (!row.resId && Object.keys(row.data).length === 0) {
        return null;
    }
    return originalRenderRow.call(this, row, index);
};

const originalX2Many = registry.category("fields").get("one2many");
const BaseX2Many = originalX2Many.component;
const oldSetup = BaseX2Many.prototype.setup;

BaseX2Many.prototype.setup = function () {
    oldSetup.call(this);

    onMounted(async () => {
        const list = this.list;
        if (list?.count > 1) {
            const newRecords = list.records.filter(r => r.resId === undefined);
            if (newRecords.length > 1) {
                for (const record of newRecords.slice(1)) {
                    await list.forget(record);
                }
                await list.model.notify();
            }
        }

        const interval = setInterval(() => {
            const containers = document.querySelectorAll(".o_list_view");
            containers.forEach(container => {
                const rows = container.querySelectorAll("tr");
                rows.forEach(row => {
                    const tds = row.querySelectorAll("td");
                    if (tds.length === 1 && tds[0].colSpan >= 3 && !tds[0].textContent.replace(/\u200B/g, "").trim()) {
                        row.remove();
                    }
                });
            });
            clearInterval(interval);
        }, 100);
    });
};