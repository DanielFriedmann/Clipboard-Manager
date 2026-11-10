from PySide6.QtWidgets import QMenu

from .links import item_link, open_link


def show_item_menu(parent, global_pos, vm, item, on_edit, on_copy):
    # Rechtsklick-Menü für Kacheln und Tabelle
    # on_copy(label) zeigt die Rückmeldung, z. B. "Benutzername kopiert"
    menu = QMenu(parent)

    menu.addAction("Eigenschaften …" if item.is_password else "Bearbeiten …", lambda: on_edit(item))
    if item.title:
        menu.addAction("Namen entfernen", lambda: vm.rename(item, "", item.username, item.url))
    menu.addSeparator()

    def copy_item():
        vm.copy(item)
        on_copy("Passwort" if item.is_password else "Eintrag")

    menu.addAction("Kopieren", copy_item)
    if item.is_password and item.username:
        menu.addAction("Benutzername kopieren",
                       lambda: (vm.copy_text(item.username), on_copy("Benutzername")))
    if item.is_password and item.url:
        menu.addAction("Adresse kopieren", lambda: (vm.copy_text(item.url), on_copy("Adresse")))
    url = item_link(item)
    if url is not None:
        menu.addAction("Link öffnen", lambda: open_link(url))
    menu.addSeparator()

    # in eine Gruppe verschieben, auch ohne Ziehen
    groups = menu.addMenu("In Gruppe verschieben")
    for group in [vm.default_group, *vm.custom_groups]:
        action = groups.addAction(group.name, lambda g=group: vm.assign_items_to_group([item], g))
        action.setEnabled(group is not item.clipboard_group)

    if item.is_password:
        menu.addAction("Kein Passwort", lambda: vm.set_password(item, False))
    else:
        menu.addAction("Als Passwort markieren", lambda: vm.set_password(item, True))
    menu.addSeparator()
    menu.addAction("Löschen", lambda: vm.delete(item))

    menu.exec(global_pos)
