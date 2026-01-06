/** @odoo-module **/

import { jsonrpc } from "@web/core/network/rpc_service";
import { renderToElement } from "@web/core/utils/render";
import options from "@web_editor/js/editor/snippets.options";

options.registry.ust_all_in_one_slider_configure = options.Class.extend({

    start: function(editMode) {
        var self = this;
        this._super.apply(this, arguments);
        self.$target.removeClass("hidden");
        self.$target.find(".ust_all_in_one_configure_slider").empty();
        if (!editMode) {
            self.$el.find(".ust_all_in_one_configure_slider").on("click", _.bind(self.getAllInOneSlider, self));
        }
    },

    onBuilt: function() {
        var self = this;
        this._super.apply(this, arguments);
        if (self.getAllInOneSlider()) {
            self.getAllInOneSlider().fail(function() {
                self.getParent()._removeSnippet();
            });
        }
    },

    cleanForSave: function() {
        $('.ust_all_in_one_configure_slider').empty();
    },

    getAllInOneSlider: function(slider_data, value) {
        var self = this;
        if (slider_data != undefined && slider_data.type == "click" || slider_data == undefined) {
            try {
                self.$input_temp = $(renderToElement("ust_common_features.ust_dynamic_popup_all_in_one_temp"));
            } catch (e) {
                console.warn("Template not found, using fallback");
                return;
            }
            self.$input_temp.appendTo('body');
            self.$input_temp.modal('show');
            var $all_s_filter = self.$input_temp.find("#popup_all_in_one_filter"),
                $all_slider_remove = self.$input_temp.find("#cancel"),
                $sub_data_all_slider = self.$input_temp.find("#ust_all_in_one_add_s");
            
            jsonrpc('/web/dataset/call', {
                model: 'all_in.one.slider',
                method: 'search_read',
                args: [],
                kwargs: {
                    fields: ['name'],
                }
            }).then(function(res) {
                $("select[id='popup_all_in_one_filter']").select2({
                    width: '95%',
                    allowClear: true,
                    placeholder: 'Slider...'
                });
                $('#popup_all_in_one_filter option[value!="0"]').remove();
                _.each(res, function(data_s) {
                    $("select[id='popup_all_in_one_filter']").append($("<option></option>").attr("value", data_s.id).attr("id", data_s.id).attr("data-display-name", data_s.slider_name).text(data_s.name));
                });
            });

            $sub_data_all_slider.on('click', function() {
                var ust_data = '';
                var cat_id = '';
                var ust_name = '';
                self.$target.attr('data-all_slider_s_id', $all_s_filter.val());
                if ($('select#popup_all_in_one_filter').find(":selected").text()) {
                    ust_data = self.$input_temp.find(":selected").text();
                    ust_name = self.$input_temp.find(":selected").attr('data-display-name');
                    cat_id = self.$input_temp.find(":selected").val();
                } else {
                    ust_data = "All In One Slider";
                }
                self.$target.empty().append('<div class="container">\
                                                <div class="ust-prod-s all-slider-header-title">\
                                                    <h3 class="ust-data-compare filter">' + ust_name + '</h3>\
                                                </div>\
                                            </div>');
            });
            $all_slider_remove.on('click', function() {
                self.getParent()._onRemoveClick($.Event("click"))
            });

        } else {
            return;
        }
    },
});

export default options.registry.ust_all_in_one_slider_configure;
