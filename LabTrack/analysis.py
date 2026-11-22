"""Обработка результатов измерений: статистика и линейная аппроксимация."""
import math
import re
import statistics

# Коэффициенты Стьюдента для доверительной вероятности 95%, df = 1..30
T95 = [12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228,
       2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093, 2.086,
       2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042]


def t_coef(n):
    df = n - 1
    if df < 1:
        return None
    return T95[df - 1] if df <= len(T95) else 1.96


def fmt(v, digits=4):
    """Число с запятой в качестве разделителя, 4 значащие цифры."""
    if v is None:
        return "—"
    return f"{v:.{digits}g}".replace(".", ",")


def describe(values):
    n = len(values)
    if n == 0:
        return None
    res = {"n": n, "mean": sum(values) / n, "min": min(values), "max": max(values)}
    if n > 1:
        sd = statistics.stdev(values)
        sem = sd / math.sqrt(n)
        res.update(sd=sd, sem=sem, ci=t_coef(n) * sem)
    return res


def linear_fit(xs, ys):
    """МНК для y = k*x + b. Возвращает None, если расчёт невозможен."""
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    k = sxy / sxx
    b = my - k * mx
    ss_res = sum((y - (k * x + b)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - my) ** 2 for y in ys)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 1.0
    res = {"k": k, "b": b, "r2": r2, "sk": None, "sb": None}
    if n > 2:
        s2 = ss_res / (n - 2)
        res["sk"] = math.sqrt(s2 / sxx)
        res["sb"] = math.sqrt(s2 * (1 / n + mx ** 2 / sxx))
    return res


def parse_number(text):
    value = float(text.strip().replace(",", ".").replace(" ", ""))
    if not math.isfinite(value):
        raise ValueError("число должно быть конечным")
    return value


def parse_pairs(text):
    """Разбор вставленного текста (например, из Excel): строки вида 'x y'.
    Возвращает (список пар, число пропущенных строк)."""
    pairs, bad = [], 0
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = [p for p in re.split(r"[\t;\s]+", line.strip()) if p]
        try:
            pairs.append((parse_number(parts[0]), parse_number(parts[1])))
        except (IndexError, ValueError):
            bad += 1
    return pairs, bad


def summary_lines(lab, ms):
    """Текстовые результаты анализа (для окна программы и отчётов)."""
    if not ms:
        return ["Нет данных для анализа. Добавьте измерения."]
    xs = [m["x"] for m in ms]
    ys = [m["y"] for m in ms]
    xn, yn = lab.get("x_name") or "x", lab.get("y_name") or "y"
    yu = f" {lab['y_unit']}" if lab.get("y_unit") else ""
    d = describe(ys)
    lines = [f"Количество измерений: {d['n']}",
             f"Среднее значение ({yn}): {fmt(d['mean'])}{yu}"]
    if "sd" in d:
        lines += [
            f"Среднеквадратичное отклонение: {fmt(d['sd'])}{yu}",
            f"Стандартная ошибка среднего: {fmt(d['sem'])}{yu}",
            f"Доверительный интервал (95%): ± {fmt(d['ci'])}{yu}",
        ]
    lines.append(f"Минимум / максимум: {fmt(d['min'])} / {fmt(d['max'])}{yu}")
    fit = linear_fit(xs, ys)
    if fit:
        lines.append(f"Линейная аппроксимация: {yn} = k·{xn} + b")
        k = f"k = {fmt(fit['k'])}" + (f" ± {fmt(fit['sk'])}" if fit["sk"] is not None else "")
        b = f"b = {fmt(fit['b'])}" + (f" ± {fmt(fit['sb'])}" if fit["sb"] is not None else "")
        lines += [k, b, f"Коэффициент детерминации R² = {fmt(fit['r2'])}"]
    elif len(ms) >= 2:
        lines.append("Аппроксимация невозможна: все значения x одинаковы.")
    return lines
