$(document).ready(function(){
    $(".nav-item.dropdown.position-static").on('click', function(event) {
        console.log("=====================")
        $(this).closest('.dropdown-menu.o_mega_menu').modal('show');
    })
});
$('.client').owlCarousel({
    loop:true,
    margin:10,
    nav:true,
    responsive:{
        0:{
            items:1.3
        },
        600:{
            items:3
        },
        1000:{
            items:4
        }
    }
})
$('.accessory_product').owlCarousel({
    loop:true,
    margin:10,
    nav:true,
    responsive:{
        0:{
            items:2.3
        },
        600:{
            items:3
        },
        1000:{
            items:5
        }
    }
})
odoo.define('website_freemoov.category_script', function (require) {
    "use strict";

    var ajax = require('web.ajax');
    var core = require('web.core');
    var Widget = require('web.Widget');

    $(document).ready(function () {
        $(".category-link").click(function (event) {
            event.preventDefault();
            var categoryId = $(this).data("category-id");
            var categoryName = $(this).data("category-name");
            ajax.jsonRpc('/fetch_subcategories', 'call', {category_id: categoryId})
                .then(function (data) {
                    // Populate the subcategory modal with data
                    console.log('>>>>>>>>>categoryId>>>>>>>>>>',data['sub_catg'])
                    $("#subcategoryModalTitle").text(categoryName);
                    
                    $("#subcategoryModalBody").html(data['sub_catg']);
                            
                    $("#top-menu-collapse-sub-category").modal("show");

                    
                });
        });
    });
});



