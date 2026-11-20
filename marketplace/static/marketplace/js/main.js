// Мелкая интерактивность без Bootstrap JS: бургер-меню, закрытие сообщений, вкладки.
document.addEventListener('DOMContentLoaded', function () {
  var toggle = document.querySelector('.nav-toggle');
  var menu = document.querySelector('.nav-menu');
  if (toggle && menu) {
    toggle.addEventListener('click', function () {
      var open = menu.classList.toggle('open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  document.querySelectorAll('.alert-close').forEach(function (btn) {
    btn.addEventListener('click', function () { btn.closest('.alert').remove(); });
  });

  // Вкладки: <button class="tab" data-tab="id"> показывает <div data-panel="id">
  document.querySelectorAll('[data-tabs]').forEach(function (box) {
    var tabs = box.querySelectorAll('.tab');
    tabs.forEach(function (tab) {
      tab.addEventListener('click', function () {
        tabs.forEach(function (t) { t.classList.toggle('active', t === tab); });
        box.querySelectorAll('[data-panel]').forEach(function (p) {
          p.classList.toggle('hidden', p.dataset.panel !== tab.dataset.tab);
        });
        if (history.replaceState) history.replaceState(null, '', '#' + tab.dataset.tab);
      });
    });
    var start = location.hash.slice(1);
    var first = box.querySelector('.tab[data-tab="' + start + '"]') || tabs[0];
    if (first) first.click();
  });
});
// Мини-скрипт интерфейса (без библиотек): бургер-меню и закрытие уведомлений.
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
})();
