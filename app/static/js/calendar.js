// Календарь выбора дат: занятые (одобренные) периоды недоступны для выбора.
(function () {
    var root = document.getElementById('calendar');
    if (!root) return;

    var inIn = document.getElementById('check_in');
    var inOut = document.getElementById('check_out');
    var busy = JSON.parse(root.getAttribute('data-busy') || '[]');
    var today = iso2date(root.getAttribute('data-today'));
    var MONTHS = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль',
                  'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];
    var DOW = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

    function iso2date(s) { var p = s.split('-'); return new Date(+p[0], +p[1] - 1, +p[2]); }
    function key(d) { return d.getFullYear() * 10000 + (d.getMonth() + 1) * 100 + d.getDate(); }
    function fmt(d) {
        var dd = ('0' + d.getDate()).slice(-2), mm = ('0' + (d.getMonth() + 1)).slice(-2);
        return dd + '.' + mm + '.' + d.getFullYear();
    }
    function parse(s) {
        var m = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(s || '');
        if (!m) return null;
        var d = new Date(+m[3], +m[2] - 1, +m[1]);
        return d.getDate() === +m[1] ? d : null;
    }
    function addDays(d, n) { return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n); }

    var periods = busy.map(function (p) { return [key(iso2date(p[0])), key(iso2date(p[1]))]; });
    // ночь дня d занята, если start <= d < end у одобренной брони
    function nightBusy(d) {
        var k = key(d);
        return periods.some(function (p) { return k >= p[0] && k < p[1]; });
    }
    function rangeFree(start, end) { // все ночи [start, end) свободны
        for (var d = start; key(d) < key(end); d = addDays(d, 1)) if (nightBusy(d)) return false;
        return true;
    }

    var start = parse(inIn.value), end = parse(inOut.value);
    var view = new Date((start || today).getFullYear(), (start || today).getMonth(), 1);

    function pick(d) {
        if (!start || end) { start = d; end = null; }
        else if (key(d) > key(start)) { end = d; }
        else { start = d; end = null; }
        inIn.value = start ? fmt(start) : '';
        inOut.value = end ? fmt(end) : '';
        render();
    }

    function render() {
        root.innerHTML = '';
        var head = document.createElement('div');
        head.className = 'cal-head';
        var prev = btn('‹', function () { view = new Date(view.getFullYear(), view.getMonth() - 1, 1); render(); });
        var next = btn('›', function () { view = new Date(view.getFullYear(), view.getMonth() + 1, 1); render(); });
        var title = document.createElement('span');
        title.textContent = MONTHS[view.getMonth()] + ' ' + view.getFullYear();
        head.appendChild(prev); head.appendChild(title); head.appendChild(next);
        root.appendChild(head);

        var grid = document.createElement('div');
        grid.className = 'cal-grid';
        DOW.forEach(function (n) {
            var c = document.createElement('div'); c.className = 'cal-dow'; c.textContent = n; grid.appendChild(c);
        });
        var offset = (new Date(view.getFullYear(), view.getMonth(), 1).getDay() + 6) % 7;
        for (var i = 0; i < offset; i++) {
            var e = document.createElement('button'); e.type = 'button';
            e.className = 'cal-day empty'; e.disabled = true; grid.appendChild(e);
        }
        var last = new Date(view.getFullYear(), view.getMonth() + 1, 0).getDate();
        for (var n = 1; n <= last; n++) {
            var d = new Date(view.getFullYear(), view.getMonth(), n);
            var b = document.createElement('button');
            b.type = 'button'; b.textContent = n; b.className = 'cal-day';
            b.setAttribute('data-date', fmt(d));
            var selectingEnd = start && !end;
            var ok;
            if (selectingEnd && key(d) > key(start)) ok = rangeFree(start, d);
            else ok = key(d) >= key(today) && !nightBusy(d);
            var isBusy = key(d) >= key(today) && nightBusy(d);
            if (isBusy) b.classList.add('busy');
            if (start && key(d) === key(start)) b.classList.add('selected');
            else if (end && key(d) === key(end)) b.classList.add('selected');
            else if (start && end && key(d) > key(start) && key(d) < key(end)) b.classList.add('in-range');
            if (!ok) b.disabled = true;
            else (function (dd) { b.addEventListener('click', function () { pick(dd); }); })(d);
            grid.appendChild(b);
        }
        root.appendChild(grid);
    }

    function btn(t, fn) {
        var b = document.createElement('button'); b.type = 'button'; b.textContent = t;
        b.addEventListener('click', fn); return b;
    }

    // ручной ввод тоже обновляет календарь
    [inIn, inOut].forEach(function (el) {
        el.addEventListener('change', function () {
            start = parse(inIn.value); end = parse(inOut.value);
            if (start) view = new Date(start.getFullYear(), start.getMonth(), 1);
            render();
        });
    });
    render();
})();
