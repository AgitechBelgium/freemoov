/** @odoo-module **/

/**
 * UST All-in-One Slider Plugin pour Odoo 19
 * 
 * Ce plugin gère la configuration du snippet "All In One Slider" dans l'éditeur de site web.
 * Il permet de sélectionner un slider configuré dans le backend.
 */

import { Plugin } from "@html_editor/plugin";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { BaseOptionComponent, useDomState } from "@html_builder/core/utils";
import { BuilderAction } from "@html_builder/core/builder_action";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart } from "@odoo/owl";

/**
 * Composant d'option pour configurer le slider All-in-One
 */
export class UstAllInOneSliderOption extends BaseOptionComponent {
    static template = "ust_common_features.UstAllInOneSliderOption";
    static selector = ".ust_all_in_one_configure_slider";
    
    setup() {
        super.setup();
        this.state = useState({
            sliders: [],
            selectedSliderId: null,
            loading: true,
        });
        
        onWillStart(async () => {
            await this.loadSliders();
        });
    }
    
    async loadSliders() {
        try {
            const sliders = await rpc('/web/dataset/call_kw/all_in.one.slider/search_read', {
                model: 'all_in.one.slider',
                method: 'search_read',
                args: [[]],
                kwargs: {
                    fields: ['id', 'name', 'slider_name'],
                }
            });
            this.state.sliders = sliders;
            this.state.loading = false;
            
            // Récupérer le slider actuellement sélectionné
            const currentId = this.editingElement?.getAttribute('data-all_slider_s_id');
            if (currentId) {
                this.state.selectedSliderId = parseInt(currentId);
            }
        } catch (error) {
            console.error('[UST] Failed to load sliders:', error);
            this.state.loading = false;
        }
    }
    
    onSliderChange(event) {
        const sliderId = event.target.value;
        this.state.selectedSliderId = sliderId ? parseInt(sliderId) : null;
        
        if (this.editingElement) {
            this.editingElement.setAttribute('data-all_slider_s_id', sliderId || '');
            
            // Mettre à jour le titre affiché
            const selectedSlider = this.state.sliders.find(s => s.id === parseInt(sliderId));
            const titleEl = this.editingElement.querySelector('.filter');
            if (titleEl && selectedSlider) {
                titleEl.textContent = selectedSlider.slider_name || selectedSlider.name;
            }
        }
    }
}

/**
 * Action pour configurer le slider
 */
export class ConfigureSliderAction extends BuilderAction {
    static id = "configureSlider";
    
    setup() {
        this.preview = false;
    }
    
    async apply({ editingElement, params }) {
        const sliderId = params?.sliderId;
        if (sliderId && editingElement) {
            editingElement.setAttribute('data-all_slider_s_id', sliderId);
        }
    }
}

/**
 * Plugin principal pour le slider All-in-One
 */
export class UstAllInOneSliderPlugin extends Plugin {
    static id = "ustAllInOneSlider";
    static dependencies = ["builderOptions"];
    
    /** @type {import("plugins").WebsiteResources} */
    resources = {
        builder_options: [
            UstAllInOneSliderOption,
        ],
        builder_actions: {
            ConfigureSliderAction,
        },
    };
}

// Enregistrer le plugin
registry.category("website-plugins").add(UstAllInOneSliderPlugin.id, UstAllInOneSliderPlugin);

export default UstAllInOneSliderPlugin;
