/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { jsonrpc } from "@web/core/network/rpc_service";

publicWidget.registry.ust_all_in_one_slider_configure = publicWidget.Widget.extend({
    selector: ".ust_all_in_one_configure_slider",
    disabledInEditableMode: true,

    start: async function() {
        var self = this;
        await this._super(...arguments);
        
        if (this.editableMode) {
            var all_in_one_data = $('#wrapwrap').find($('[id="ust_all_in_one_configure"]'));
            var ust_slider_name = "";
            _.each(all_in_one_data, function ($all_s){
                $($all_s).empty().append('<div class="container">\
                                                <div class="ust-prod-s all-slider-header-title">\
                                                    <h3 class="filter">' + ust_slider_name + '</h3>\
                                                </div>\
                                            </div>')
            });
        }
        
        if (!this.editableMode) {
            var all_slider_id = self.$target.attr('data-all_slider_s_id');
            $.get("/slider_s/all_in_one_data", {
                'style_id': all_slider_id || '',
            }).then(function(ust_slider_record) {
                if (ust_slider_record) {
                    self.$target.empty();
                    self.$target.append(ust_slider_record);
                    $(".ust_all_in_one_configure_slider").removeClass('o_hidden');
                    jsonrpc('/slider_s/get_all_slider_time_data', {
                        'all_slider_id': all_slider_id
                    }).then(function(ust_slider) {
                        self.getOwlAllInOneSlider(ust_slider);
                    });
                }
            });
        }
    },

    getOwlAllInOneSlider: function (ust_slider) {
        $('div#' + ust_slider.slider_id).owlCarousel({
            margin: 20,
            navText: [
                '<i class="fa fa-angle-left"></i>',
                '<i class="fa fa-angle-right"></i>'
            ],
            items: ust_slider.no_counts,
            rewind: true,
            dots: false,
            autoplayHoverPause: true,
            responsiveClass: true,
            nav: true,
            autoplay: ust_slider.slider_auto_slide,
            loop: false,
            autoplayTimeout: ust_slider.slider_auto_play_time,
            mouseDrag: true,
            touchDrag: true,
            responsive: {
                0: {
                    items: 2,
                },
                420: {
                    items: 2,
                },
                768: {
                    items: 2,
                },
                1000: {
                    items: 3,
                },
                1500: {
                    items: ust_slider.no_counts,
                },
            },
        });
        
        setTimeout(function(){
            var sliderimgheight = $('.ust_prod_items .ust_prod_items_img a').width(); 
            $('.ust_prod_items .ust_prod_items_img a').height(sliderimgheight);
        }, 410);
        
        // Lazy loading for images
        (function () {
            var observer = new IntersectionObserver(onIntersect);
            document.querySelectorAll("#ust_all_in_one_configure img[data-lazy]").forEach((img) => {
                observer.observe(img);
            });

            function onIntersect(entries) {
                entries.forEach((entry) => {
                    if (entry.target.getAttribute("data-processed") || !entry.isIntersecting)
                        return true;
                    entry.target.setAttribute("src", entry.target.getAttribute("data-src"));
                    entry.target.setAttribute("data-processed", true);
                });
            }
        })();
        
        // Notification toast reload
        $(function() {
            if($(".notification_toast_modal_show").length > 0){
                $('form[action="/shop/cart/update"] a.a-submit, form[action="/shop/cart/update"] a#add_to_cart').click(function() {
                   setTimeout(function () {
                        location.reload();
                    }, 3000);
                });
            }
        });
    },
});

export default publicWidget.registry.ust_all_in_one_slider_configure;
