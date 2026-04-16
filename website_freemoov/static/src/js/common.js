/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

// Override Odoo's product carousel widget:
// - Update CSS variable for sticky top instead of setting inline style
// - Disable _onMouseWheel (scroll should scroll the page, not cycle slides)
if (publicWidget.registry.websiteSaleCarouselProduct) {
    publicWidget.registry.websiteSaleCarouselProduct.include({
        _updateCarouselPosition() {
            // Set sticky top on parent based on fixed header height
            let size = 5;
            // When affixed, header loses o_top_fixed_element — check both
            const header = document.querySelector('header.o_header_affixed');
            if (header) {
                size += $(header).outerHeight();
            } else {
                for (const el of document.querySelectorAll('.o_top_fixed_element')) {
                    size += $(el).outerHeight();
                }
            }
            const parent = this.$el.closest('.o_wsale_product_images')[0];
            if (parent) {
                parent.style.setProperty('top', size + 'px');
            }
        },
        _onMouseWheel() {
            // No-op: let page scroll normally
        },
    });
}

$(document).ready(function(){
    $('.attribute_name').each(function() {
        var el = $(this);
        el.text(el.text().replace(/[\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{FE00}-\u{FE0F}\u{200D}\u{20E3}\u{E0020}-\u{E007F}]/gu, '').trim());
    });

    var $offcanvas = $('#freemoov-offcanvas');
    if ($offcanvas.length && $offcanvas.closest('header').length) {
        $offcanvas.appendTo('body');
    }

    // Mega-menu hover intent: keep panel open while mouse traverses the gap
    // between the trigger and the absolute-positioned panel.
    var megaHoverTimeout = null;
    $(document).on('mouseenter', '.fm-mega-trigger, .fm-mega-panel', function() {
        if (megaHoverTimeout) {
            clearTimeout(megaHoverTimeout);
            megaHoverTimeout = null;
        }
        var $trigger = $(this).hasClass('fm-mega-trigger')
            ? $(this)
            : $(this).closest('.fm-mega-trigger');
        $('.fm-mega-trigger.show').not($trigger).removeClass('show');
        $trigger.addClass('show');
    });
    $(document).on('mouseleave', '.fm-mega-trigger, .fm-mega-panel', function() {
        if (megaHoverTimeout) clearTimeout(megaHoverTimeout);
        megaHoverTimeout = setTimeout(function() {
            $('.fm-mega-trigger.show').removeClass('show');
        }, 150);
    });

    $(".nav-item.dropdown.position-static").on('click', function(event) {
        $(this).closest('.dropdown-menu.o_mega_menu').modal('show');
    });
    if($('div').hasClass('cat-div')) {
        $('.cat-div').parent().find('#ust_all_in_one_configure').addClass('bg-white');
    }
    
    // Owl Carousel initialization
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
    
    // Category script
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
    
    $(".back_to_menu").click(function() {
        $("#top-menu-collapse").modal("show");
        $("#top-menu-collapse-sub-category").modal("hide");
        $(".top_menu_sub_categ").modal("hide");
    });
    
    $(".cat-div").parents('#ust_all_in_one_configure').css("background-color", "#fff");
    if($('div').hasClass('cat-div')) {
        $('.cat-div').parent().find('#ust_all_in_one_configure').addClass('bg-white');
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

    
    // Product detail: ensure no ancestor has overflow:hidden that would break sticky
    // CSS handles sticky via position:sticky on .o_wsale_product_images (desktop only)

    $(".category-link").click(function (event) {
        event.preventDefault();
        var categoryId = $(this).data("category-id");
        var categoryName = $(this).data("category-name");
        fetch('/fetch_subcategories', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                jsonrpc: '2.0',
                method: 'call',
                params: { category_id: categoryId }
            })
        })
        .then(function(response) { return response.json(); })
        .then(function(result) {
            var data = result.result;
            var category_html = "<a class='nav_link text-white' href='/shop/category/" + data['category'] + "'>" + categoryName + "</a>";
            $("#subcategoryModalTitle").find('a').html(category_html);
            var link = "/shop/category/" + data['category'];
            $(".sub_categ_button").find('a').attr('href', link);
            $("#subcategoryModalBody").html(data['sub_catg']);
            $("#top-menu-collapse-sub-category").modal("show");
        });
    });
});

