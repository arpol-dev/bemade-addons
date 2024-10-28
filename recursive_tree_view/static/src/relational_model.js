/** @odoo-module **/

import {RelationalModel} from '@web/model/relational_model/relational_model';
import {patch} from '@web/core/utils/patch';
import {
    getFieldsSpec,
    makeActiveField,
    getBasicEvalContext
} from "@web/model/relational_model/utils";

patch(RelationalModel.prototype, 'recursive-list-extension', {
    /**
     * Override to add child record tracking.
     * Fetches records and marks records with `hasChildren` if they have child records.
     */
    async _loadRecords(config, evalContext = config.context) {
        const {resModel, resIds, activeFields, fields, context} = config;
        const parentField = await this.orm.call(
            'parent.field.service',
            'get_parent_field',
            [resModel],
        );
        activeFields[parentField] = makeActiveField()
        const records = await super._loadRecords(config, evalContext);
        // Get the parent ID field if there is one
        if (records && parentField) {
            const fieldSpec = getFieldsSpec(activeFields, fields, evalContext);
            // Fetch records with the additional field
            const parentIds = resIds
            const children = await this.orm.webSearchRead(resModel, [[parentField, "in", parentIds]], {
                context: {bin_size: true, ...context},
                specification: fieldSpec,
            });

            // Track children by grouping child records under each parent
            const childrenByParent = {};
            for (const child of children) {
                const parentId = child[parentField];
                if (parentId) {
                    if (!childrenByParent[parentId]) {
                        childrenByParent[parentId] = [];
                    }
                    childrenByParent[parentId].push(child);
                }
            }

            records.forEach(record => {
                record.children = new this.constructor.DynamicRecordList(this, config, childrenByParent[record.resId]);
            });
        }
        return records;
    },

    /**
     * Fetch and load child records dynamically for a given parent record ID.
     * Adds children to the model’s records to ensure they’re tracked in the model’s state.
     * @param {number} parentId - The ID of the parent record.
     * @returns {Promise<Array>} - List of child records as model records.
     */
    async fetchChildren(parentId) {
        const config = self.config
        const {resModel, resIds, activeFields, fields, context} = config;
        const evalContext = getBasicEvalContext(config);
        const fieldSpec = getFieldsSpec(activeFields, fields, evalContext);
        const parentRecord = this.root.records.find((r) => r.resId == parentId)
        if (!parentRecord) {
            throw Error("Attempt to find parent record failed.");
        }
        // Fetch child records where `parent_id` matches the given `parentId`
        const childrenData = await this.orm.webSearchRead(resModel, [[this.parentField, '=', parentId]], {
            context: context,
            specification: fieldSpec,
        });
        if (childrenData) {
            parentRecord.children = new this.constructor.DynamicRecordList(this, this.config, childrenData);
        }
        return parentRecord.children;
    },

});
