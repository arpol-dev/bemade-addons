/** @odoo-module **/

import {ListController} from '@web/views/list/list_controller';
import {patch} from '@web/core/utils/patch';
import {useService} from '@web/core/utils/hooks';
import {onWillRender} from '@odoo/owl';
import {useBus} from "@web/core/utils/hooks";

patch(ListController.prototype, {
    async setup() {
        useBus(this.env.bus, "expandRow", this.onExpandRow)
        useBus(this.env.bus, "collapseRow", this.onCollapseRow)
        super.setup();
        if (this.props.archInfo.recursive) {
            // Fetch the parent field from the model
            const parentField = await this.orm.call(
                'parent.field.service',
                'get_parent_field',
                [this.props.resModel],
            );

            // Validate the parentField and adjust archInfo accordingly
            if (parentField) {
                // If parentField is valid, store it and continue with recursive setup
                this.parentField = parentField;
                this.props.archInfo.parentField = parentField;
            } else {
                // If no valid parentField, disable recursion and childField functionality
                this.props.archInfo.recursive = false;
                delete this.props.archInfo.childField;
            }

            // Proceed with recursive setup if recursive is enabled
            if (this.props.archInfo.recursive) {
                this.childrenByParent = {};  // Cache for loaded children

                // Bind event listeners for expand and collapse
                this.model.hooks.onRootLoaded = async () => {
                    const rootRecords = this.model.root.records;
                    const rootIds = rootRecords.map(record => record.resId)
                    const childRecords = await this.orm.searchRead(
                        this.props.resModel,
                        [[this.parentField, 'in', rootIds]],
                        [],
                    )
                    const rootIdsWithChildren = new Set(childRecords.map(child => child[this.parentField]));
                    rootRecords.forEach(record => {
                        record.data.hasChildren = rootIdsWithChildren.has(record.data.resId);
                    });
                }
            }
        }
    },

    async fetchChildren(parentId) {
        if (this.childrenByParent[parentId]) {
            return this.childrenByParent[parentId];
        }

        const children = await this.rpc({
            model: this.props.resModel,
            method: 'search_read',
            args: [[this.parentField, '=', parentId]],
            kwargs: {fields: ['id', 'name', this.parentField]},
        });

        this.childrenByParent[parentId] = children;
        return children;
    },

    async onExpandRow(event) {
        const {parentId} = event.data;
        const children = await this.fetchChildren(parentId);
        this.renderer.renderChildrenRows(children, parentId);
    },

    onCollapseRow(event) {
        const {parentId} = event.data;
        this.renderer.removeChildrenRows(parentId);
    },
});
