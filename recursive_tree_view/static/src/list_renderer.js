/** @odoo-module **/

import { ListRenderer } from '@web/views/list/list_renderer';
import { patch } from '@web/core/utils/patch';

patch(ListRenderer.prototype, {
    setup() {
        super.setup();
        this.recursive = this.props.archInfo.recursive;
    },

    async _onExpandClick(ev) {
        const $button = $(ev.currentTarget);
        const isExpanded = $button.hasClass('expanded');
        $button.toggleClass('expanded', !isExpanded).text(isExpanded ? '+' : '-');

        const parentId = $button.data('expand');
        if (!isExpanded) {
            // Emit an event to request the controller to expand the row
            this.env.bus.trigger('expandRow', { parentId });
        } else {
            // Emit an event to request the controller to collapse the row
            this.env.bus.trigger('collapseRow', { parentId });
        }
    },

    renderChildrenRows(children, parentId) {
        const $parentRow = this.$(`tr[data-id="${parentId}"]`);
        const parentDepth = $parentRow.data('depth') || 0;

        children.forEach(child => {
            const $row = $('<tr>')
                .attr('data-id', child.id)
                .attr('data-parent-id', parentId)
                .attr('data-depth', parentDepth + 1)
                .attr('data-has-children', child.hasChildren)
                .addClass('o_recursive_child_row')
                .css('padding-left', `${(parentDepth + 1) * 20}px`);

            for (const [fieldName, fieldValue] of Object.entries(child)) {
                const $cell = $('<td>').text(fieldValue);
                $row.append($cell);
            }

            $parentRow.after($row);
        });
    },

    removeChildrenRows(parentId) {
        const childRows = this.$(`tr[data-parent-id="${parentId}"]`);

        childRows.each((index, childRow) => {
            const childId = $(childRow).data('id');
            this.removeChildrenRows(childId);
        });

        childRows.remove();
    },
});
