odoo.define('website_freemoov.carousel_override', function (require) {
    "use strict";
    var publicWidget = require('web.public.widget');
    var dom = require('web.dom');

    // Override Odoo's product carousel widget:
    // - Move sticky from #o-carousel-product to parent .o_wsale_product_images
    // - Use Odoo's dom.scrollFixedOffset() for reliable header height detection
    // - Disable _onMouseWheel (scroll should scroll the page, not cycle slides)
    if (publicWidget.registry.websiteSaleCarouselProduct) {
        publicWidget.registry.websiteSaleCarouselProduct.include({
            _updateCarouselPosition: function () {
                // Use Odoo's built-in fixed offset calculation (handles all header states)
                var offset = dom.scrollFixedOffset() + 5;
                // Apply sticky top to the parent images container instead of the carousel
                var parent = this.$el.closest('.o_wsale_product_images')[0];
                if (parent) {
                    parent.style.setProperty('top', offset + 'px');
                }
            },
            _onMouseWheel: function () {
                // No-op: let page scroll normally
            },
        });
    }
});

$(document).ready(function(){
    $(".nav-item.dropdown.position-static").on('click', function(event) {
        $(this).closest('.dropdown-menu.o_mega_menu').modal('show');
    });
    if($('div').hasClass('cat-div')) {
        $('.cat-div').parent().find('#ust_all_in_one_configure').addClass('bg-white');
    }

    // Owl Carousel initialization (with .length guards)
    if ($('.client').length) {
        $('.client').owlCarousel({
            loop: true,
            margin: 10,
            nav: true,
            responsive: {
                0: { items: 1.3 },
                600: { items: 3 },
                1000: { items: 4 }
            }
        });
    }

    if ($('.accessory_product').length) {
        $('.accessory_product').owlCarousel({
            loop: true,
            margin: 10,
            nav: true,
            responsive: {
                0: { items: 2.3 },
                600: { items: 3 },
                1000: { items: 5 }
            }
        });
    }

    // Replace download button with share button on product page
    var $downloadBtn = $('.download_product_img');
    if ($downloadBtn.length) {
        var $shareBtn = $(
            '<div class="share_product_link">' +
                '<a class="share_link_btn" href="#" title="Copier le lien">' +
                    '<i class="fa fa-share-alt"></i>' +
                '</a>' +
                '<span class="share_tooltip">Lien copié !</span>' +
            '</div>'
        );
        $downloadBtn.after($shareBtn);
        $downloadBtn.hide();
    }

    $(document).on('click', '.share_link_btn', function(e) {
        e.preventDefault();
        var url = window.location.href;
        var $tooltip = $(this).siblings('.share_tooltip');
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(url).then(function() {
                $tooltip.addClass('show');
                setTimeout(function() { $tooltip.removeClass('show'); }, 2000);
            });
        } else {
            var $temp = $('<input>');
            $('body').append($temp);
            $temp.val(url).select();
            document.execCommand('copy');
            $temp.remove();
            $tooltip.addClass('show');
            setTimeout(function() { $tooltip.removeClass('show'); }, 2000);
        }
    });
});

odoo.define('website_freemoov.category_script', function (require) {
    "use strict";

    var ajax = require('web.ajax');
    var core = require('web.core');
    var Widget = require('web.Widget');

    $(document).ready(function () {
        $('#o_product_page_reviews_content').addClass('show');
        $(".ust-all-slider .owl-item").each(function () {
            if ($(this).find("del").length > 0) {
                $(this).find('.oe_price').css('color', '#dc3545');
                $(this).find('.oe_price').addClass('main_price');
            }
        });
        $('.product_price').each(function() {
            if ($(this).find('del').length) {
                $(this).find('span.h6').css('color', '#dc3545');
            } else {
                $(this).find('span.h6').css('color', '#000');
            }
        });
        $(".cat-div").parents('#ust_all_in_one_configure').css("background-color", "#fff");
        if($('div').hasClass('cat-div')) {
            $('.cat-div').parent().find('#ust_all_in_one_configure').addClass('bg-white');
        }

        // Desktop mega-menu: show/hide on hover with delay
        var megaTimeout;
        $('.fm-mega-trigger').on('mouseenter', function() {
            clearTimeout(megaTimeout);
            $('.fm-mega-trigger').removeClass('show');
            $(this).addClass('show');
        }).on('mouseleave', function() {
            var $el = $(this);
            megaTimeout = setTimeout(function() {
                $el.removeClass('show');
            }, 200);
        });

        // Mobile search toggle
        $('.fm-search-toggle').on('click', function() {
            $('#fm-search-collapse').collapse('toggle');
        });

        // Close offcanvas when clicking a navigation link (page will reload)
        $('#freemoov-offcanvas').on('click', 'a[href]:not([href="#"])', function() {
            $('#freemoov-offcanvas').removeClass('show');
            $('.offcanvas-backdrop').remove();
            $('body').css('overflow', '');
        });
    });
});
