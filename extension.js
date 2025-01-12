import GObject from 'gi://GObject';
import St from 'gi://St';
import GLib from 'gi://GLib';

import { Extension, gettext as _ } from'resource:///org/gnome/shell/extensions/extension.js';
import * as PanelMenu from'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from'resource:///org/gnome/shell/ui/popupMenu.js';

import * as Main from'resource:///org/gnome/shell/ui/main.js';

// Путь к каталогу расширения
const EXTENSION_PATH = `${GLib.get_home_dir()}/.local/share/gnome-shell/extensions/kayako@activecloud.com`;

// Путь к Python и скрипту
const PYTHON_EXECUTABLE = `${EXTENSION_PATH}/.venv/bin/python`;
const SCRIPT_PATH = `${EXTENSION_PATH}/request.py`;

// Команда для выполнения
const KAYAKO_NOTIFICATIONS_SCRIPT_PATH = `"${PYTHON_EXECUTABLE}" "${SCRIPT_PATH}"`;

const truncateText = (text, maxLength) => {
    return text.length > maxLength? text.substring(0, maxLength) + '...' : text;
};

const Indicator = GObject.registerClass(
class Indicator extends PanelMenu.Button {
    _init() {
        super._init(0.0, _('Levels Indicator'));

        this.levels = [];
        this.menuItems = [];

        this.label = new St.Label({
            text: '0',
            style_class: 'number-indicator',
        });
        this.add_child(this.label);

        this._updateLevels();
        this._createMenuItems();
        this._updateUI();

        this.timeout = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 180000, () => {
            this._updateLevels();
            this._updateUI();
            return GLib.SOURCE_CONTINUE;
        });
    }

    _updateLevels() {
        this.levels = [];
    
        try {
            const [res, stdout] = GLib.spawn_command_line_sync(KAYAKO_NOTIFICATIONS_SCRIPT_PATH);
    
            if (res) {
                const output = JSON.parse(stdout);
                this.levels = output.levels || [];
                this.total = output.total || 0;
            } else {
                logError(new Error('Ошибка выполнения Python-скрипта'));
            }
        } catch (e) {
            logError(e);
            this.levels = [];
            this.total = 0;
        }
        // Убедитесь, что обновление UI происходит после обновления уровней
        this._createMenuItems();
        this._updateUI();
    }

    _createMenuItems() {
        this.menu.removeAll();
        this.menuItems = [];

        this.levels.forEach(({ level, value, details }) => {
            const box = new St.BoxLayout({ x_expand: true, style_class:'menu-item-box' });

            const textLabel = new St.Label({
                text: level,
                x_expand: true,
                style_class:'menu-item-text',
            });

            const valueLabel = new St.Label({
                text: `${value}`,
                style_class:'menu-item-value',
            });

            box.add_child(textLabel);
            box.add_child(valueLabel);

            const parentItem = new PopupMenu.PopupSubMenuMenuItem('');
            parentItem.actor.add_child(box);

            details.forEach(({ id, subject }) => {
                const url = `https://my.activecloud.com/ru/staff/index.php?/Tickets/Ticket/View/${id}`;
                const childLink = new St.Label({
                    text: subject,
                    style_class:'submenu-item-link',
                    reactive: true,
                });

                childLink.connect('button-press-event', () => {
                    GLib.spawn_command_line_async(`xdg-open ${url}`);
                });

                const childItem = new PopupMenu.PopupBaseMenuItem();
                childItem.actor.add_child(childLink);

                parentItem.menu.addMenuItem(childItem);
            });

            this.menuItems.push({ parentItem, valueLabel });
            this.menu.addMenuItem(parentItem);
        });
    }

    _updateUI() {
        // Обновление метки общего числа
        this.label.set_text(`${this.total}`);
    
        // Обновление существующих элементов меню
        this.levels.forEach(({ value, details }, index) => {
            const menuItem = this.menuItems[index];
    
            if (menuItem) {
                menuItem.valueLabel.set_text(`${value}`);
                menuItem.parentItem.menu.removeAll();
    
                details.forEach(({ id, subject }) => {
                    const truncatedSubject = truncateText(subject, 45);
                    const url = `https://my.activecloud.com/ru/staff/index.php?/Tickets/Ticket/View/${id}`;
                    const childLink = new St.Label({
                        text: truncatedSubject,
                        style_class: 'submenu-item-link',
                        reactive: true,
                    });
    
                    childLink.connect('button-press-event', () => {
                        GLib.spawn_command_line_async(`xdg-open ${url}`);
                    });
    
                    const childItem = new PopupMenu.PopupBaseMenuItem();
                    childItem.actor.add_child(childLink);
                    menuItem.parentItem.menu.addMenuItem(childItem);
                });
            }
        });
    
        // Удаление лишних элементов меню, если уровней стало меньше
        if (this.menuItems.length > this.levels.length) {
            this.menuItems.splice(this.levels.length).forEach(({ parentItem }) => {
                parentItem.destroy();
            });
        }
    }

    destroy() {
        if (this.timeout) {
            GLib.Source.remove(this.timeout);
            this.timeout = null;
        }
        super.destroy();
    }
});

export default class SupportTicketsExtension extends Extension {
    enable() {
        this.indicator = new Indicator();
        Main.panel.addToStatusArea(this.uuid, this.indicator);
    }

    disable() {
        this.indicator.destroy();
        this.indicator = null;
    }
}