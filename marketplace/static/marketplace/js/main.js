// Мини-скрипт интерфейса (без библиотек): бургер-меню, закрытие уведомлений, вкладки профиля.
(function () {
    'use strict';

    var header = document.querySelector('.site-header');
    var toggle = document.querySelector('.nav-toggle');
    if (header && toggle) {
        toggle.addEventListener('click', function () {
            var open = header.classList.toggle('is-open');
            toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
        });
    }

    document.querySelectorAll('.alert-close').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var alert = btn.closest('.alert');
            if (alert) { alert.remove(); }
        });
    });

    // Вкладки: <button class="tab" data-tab="id"> показывает <div data-panel="id">
    document.querySelectorAll('[data-tabs]').forEach(function (box) {
        var tabs = box.querySelectorAll('.tab');
        function show(tab) {
            tabs.forEach(function (t) { t.classList.toggle('active', t === tab); });
            box.querySelectorAll('[data-panel]').forEach(function (p) {
                p.classList.toggle('hidden', p.dataset.panel !== tab.dataset.tab);
            });
        }
        tabs.forEach(function (tab) {
            tab.addEventListener('click', function () {
                show(tab);
                if (history.replaceState) { history.replaceState(null, '', '#' + tab.dataset.tab); }
            });
        });
        var start = box.querySelector('.tab[data-tab="' + location.hash.slice(1) + '"]');
        if (start) { show(start); box.scrollIntoView(); } else if (tabs[0]) { show(tabs[0]); }
    });
})();
