/** @odoo-module **/

import publicWidget from "web.public.widget";
import "website_sale.website_sale";
import {qweb as QWeb} from "web.core";

const totalItems = $('.carousel-item').length;
var currentIndex = $('.carousel-item.active').index() + 1;
$('.carousel_product_num').html('' + currentIndex + '/' + totalItems + '');
var down_index;

const websiteSaleCarouselProductWidget = publicWidget.registry.websiteSaleCarouselProduct;

    $(".download_img").click(function(){
        var product_img = $('#o-carousel-product').find(".carousel-item.active").find('.product_detail_img');
        var img_src = $(product_img).attr("src")
        $(this).attr("download", img_src).attr("href", img_src);
    });

    websiteSaleCarouselProductWidget.include({
        selector: '#o-carousel-product',
        events: _.extend({
            "click .carousel-control-next": "_onNextClick",
            "click .carousel-control-prev": "_onPrevClick",
        }, websiteSaleCarouselProductWidget.prototype.events),

        _onNextClick: function (ev) {
            var currentIndex_active = $('.carousel-item.active').index() + 2;
            if (totalItems >= currentIndex_active)
            {
                down_index= $('.carousel-item.active').index() + 2;
                $('.carousel_product_num').html(''+currentIndex_active+'/'+totalItems+'');
            }  
        },
        _onPrevClick: function (ev) {
            down_index=down_index-1;
                if (down_index >= 1 )
                {
                    $('.carousel_product_num').html(''+down_index+'/'+totalItems+'');
                }
        },
        
    });
