/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

// Initialize carousel counter on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    var carousel = document.getElementById('o-carousel-product');
    if (carousel) {
        var items = carousel.querySelectorAll('.carousel-item');
        var totalItems = items.length;
        var activeItem = carousel.querySelector('.carousel-item.active');
        var currentIndex = activeItem ? Array.from(items).indexOf(activeItem) + 1 : 1;
        
        var carouselNum = document.querySelector('.carousel_product_num');
        if (carouselNum) {
            carouselNum.innerHTML = '' + currentIndex + '/' + totalItems + '';
        }
    }
});

// Download image functionality
document.addEventListener('click', function(e) {
    if (e.target && (e.target.classList.contains('download_img') || e.target.closest('.download_img'))) {
        var carousel = document.getElementById('o-carousel-product');
        if (carousel) {
            var activeItem = carousel.querySelector('.carousel-item.active');
            if (activeItem) {
                var product_img = activeItem.querySelector('.product_detail_img');
                if (product_img) {
                    var img_src = product_img.getAttribute("src");
                    var downloadLink = e.target.classList.contains('download_img') ? e.target : e.target.closest('.download_img');
                    downloadLink.setAttribute("download", img_src);
                    downloadLink.setAttribute("href", img_src);
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
            var carousel = document.getElementById('o-carousel-product');
            if (!carousel) return;
            
            var items = carousel.querySelectorAll('.carousel-item');
            var totalItems = items.length;
            
            // Wait a bit for Bootstrap to update the active class
            setTimeout(function() {
                var activeItem = carousel.querySelector('.carousel-item.active');
                var currentIndex = activeItem ? Array.from(items).indexOf(activeItem) + 1 : 1;
                
                var carouselNum = document.querySelector('.carousel_product_num');
                if (carouselNum) {
                    carouselNum.innerHTML = '' + currentIndex + '/' + totalItems + '';
                }
            }, 100);
        },
        
        _onPrevClick: function (ev) {
            var carousel = document.getElementById('o-carousel-product');
            if (!carousel) return;
            
            var items = carousel.querySelectorAll('.carousel-item');
            var totalItems = items.length;
            
            // Wait a bit for Bootstrap to update the active class
            setTimeout(function() {
                var activeItem = carousel.querySelector('.carousel-item.active');
                var currentIndex = activeItem ? Array.from(items).indexOf(activeItem) + 1 : 1;
                
                var carouselNum = document.querySelector('.carousel_product_num');
                if (carouselNum) {
                    carouselNum.innerHTML = '' + currentIndex + '/' + totalItems + '';
                }
            }, 100);
        },
    });
}
