/** @odoo-module **/

$(document).ready(function(){
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
        var priceContainer = $(this).find(".oe_price");
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
            console.log('>>>>>>>>>categoryId>>>>>>>>>>', data['sub_catg']);
            var category_html = "<a class='nav_link text-white' href='/shop/category/" + data['category'] + "'>" + categoryName + "</a>";
            $("#subcategoryModalTitle").find('a').html(category_html);
            var link = "/shop/category/" + data['category'];
            $(".sub_categ_button").find('a').attr('href', link);
            $("#subcategoryModalBody").html(data['sub_catg']);
            $("#top-menu-collapse-sub-category").modal("show");
        });
    });
});

