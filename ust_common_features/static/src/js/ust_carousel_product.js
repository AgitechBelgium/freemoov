/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

// Initialize carousel counter on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    const totalItems = document.querySelectorAll('.carousel-item').length;
    const activeItem = document.querySelector('.carousel-item.active');
    var currentIndex = activeItem ? Array.from(document.querySelectorAll('.carousel-item')).indexOf(activeItem) + 1 : 1;
    
    const carouselNum = document.querySelector('.carousel_product_num');
    if (carouselNum) {
        carouselNum.innerHTML = '' + currentIndex + '/' + totalItems + '';
    }
});

// Download image functionality
document.addEventListener('click', function(e) {
    if (e.target && e.target.classList.contains('download_img')) {
        var carousel = document.getElementById('o-carousel-product');
        if (carousel) {
            var activeItem = carousel.querySelector('.carousel-item.active');
            if (activeItem) {
                var product_img = activeItem.querySelector('.product_detail_img');
                if (product_img) {
                    var img_src = product_img.getAttribute("src");
                    e.target.setAttribute("download", img_src);
                    e.target.setAttribute("href", img_src);
                }
            }
        }
    }
});

// Check if websiteSaleCarouselProduct exists before extending
if (publicWidget.registry.websiteSaleCarouselProduct) {
    publicWidget.registry.websiteSaleCarouselProduct.include({
        selector: '#o-carousel-product',
        events: Object.assign({}, publicWidget.registry.websiteSaleCarouselProduct.prototype.events || {}, {
            "click .carousel-control-next": "_onNextClick",
            "click .carousel-control-prev": "_onPrevClick",
        }),

        _onNextClick: function (ev) {
            var totalItems = document.querySelectorAll('.carousel-item').length;
            var activeItem = document.querySelector('.carousel-item.active');
            var currentIndex_active = activeItem ? Array.from(document.querySelectorAll('.carousel-item')).indexOf(activeItem) + 2 : 2;
            
            if (totalItems >= currentIndex_active) {
                var carouselNum = document.querySelector('.carousel_product_num');
                if (carouselNum) {
                    carouselNum.innerHTML = '' + currentIndex_active + '/' + totalItems + '';
                }
            }
        },
        
        _onPrevClick: function (ev) {
            var totalItems = document.querySelectorAll('.carousel-item').length;
            var activeItem = document.querySelector('.carousel-item.active');
            var currentIndex = activeItem ? Array.from(document.querySelectorAll('.carousel-item')).indexOf(activeItem) + 1 : 1;
            
            if (currentIndex >= 1) {
                var carouselNum = document.querySelector('.carousel_product_num');
                if (carouselNum) {
                    carouselNum.innerHTML = '' + currentIndex + '/' + totalItems + '';
                }
            }
        },
    });
}