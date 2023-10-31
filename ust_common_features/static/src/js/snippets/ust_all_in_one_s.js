odoo.define('ust_common_features.ust_all_in_one_s', function(require) {
    'use strict';

    var ajax = require('web.ajax');
    var core = require('web.core');
    var qweb = core.qweb;
    var _t = core._t;
    var options = require('web_editor.snippets.options');


    options.registry.ust_all_in_one_slider_configure = options.Class.extend({

        start: function(editMode) {
            var $this = this;
            $this._super();
            $this.$target.removeClass("hidden");
            $this.$target.find(".ust_all_in_one_configure_slider").empty();
            if (!editMode) {
                $this.$el.find(".ust_all_in_one_configure_slider").on("click", _.bind($this.getAllInOneSlider, $this));
            }
        },

        onBuilt: function() {
            var $this = this;
            $this._super();
            if ($this.getAllInOneSlider()) {
                $this.getAllInOneSlider().fail(function() {
                    $this.getParent()._removeSnippet();
                });
            }
        },

        cleanForSave: function() {
            $('.ust_all_in_one_configure_slider').empty();
        },

        getAllInOneSlider: function(slider_data, value) {
            var $this = this;
            if (slider_data != undefined && slider_data.type == "click" || slider_data == undefined) {
                $this.$input_temp = $(qweb.render("ust_common_features.ust_dynamic_popup_all_in_one_temp"));
                $this.$input_temp.appendTo('body');
                $this.$input_temp.modal('show');
                var $all_s_filter = $this.$input_temp.find("#popup_all_in_one_filter"),
                    $all_slider_remove = $this.$input_temp.find("#cancel"),
                    $sub_data_all_slider = $this.$input_temp.find("#ust_all_in_one_add_s");
                    ajax.jsonRpc('/web/dataset/call', 'call', {
                        model: 'all_in.one.slider',
                        method: 'search_read',
                        args: [],
                        kwargs: {
                            fields: ['name'],
                        }
                    }).then(function(res) {
                    $("select[id='popup_all_in_one_filter']").select2({
                        width : '95%',
                        allowClear: true,
                        placeholder : 'Slider...'
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
                    $this.$target.attr('data-all_slider_s_id', $all_s_filter.val());
                    if ($('select#popup_all_in_one_filter').find(":selected").text()) {
                        ust_data = _t($this.$input_temp.find(":selected").text());
                        ust_name = _t($this.$input_temp.find(":selected").attr('data-display-name'));
                        cat_id = _t($this.$input_temp.find(":selected").val());
                    } else {
                        ust_data = _t("All In One Slider");
                    }
                    $this.$target.empty().append('<div class="container">\
                                                    <div class="ust-prod-s all-slider-header-title">\
                                                        <h3 class="ust-data-compare filter">' + ust_name + '</h3>\
                                                    </div>\
                                                </div>');
                });
                $all_slider_remove.on('click', function() {
                    $this.getParent()._onRemoveClick($.Event("click"))
                });

            } else {
                return;
            }
        },
    });
});
