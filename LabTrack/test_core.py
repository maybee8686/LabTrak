"""Проверка логики без интерфейса: python test_core.py"""
import os
import tempfile

from analysis import describe, linear_fit, parse_pairs
from db import Database
from reports import collect, export_docx, export_pdf


def approx(a, b, tol=1e-9):
    return abs(a - b) < tol


def main():
    d = describe([1, 2, 3, 4, 5])
    assert approx(d["mean"], 3) and approx(d["sd"], 1.5811388300841898)

    fit = linear_fit([1, 2, 3, 4], [3, 5, 7, 9])  # y = 2x + 1
    assert approx(fit["k"], 2) and approx(fit["b"], 1) and approx(fit["r2"], 1)
    assert linear_fit([1, 1, 1], [1, 2, 3]) is None

    pairs, bad = parse_pairs("x\ty\n1,5\t2,5\n2;4\n3 6.5\n\nabc")
    assert pairs == [(1.5, 2.5), (2.0, 4.0), (3.0, 6.5)] and bad == 2

    with tempfile.TemporaryDirectory() as tmp:
        db = Database(os.path.join(tmp, "t.db"))
        lab_id = db.add_lab("Закон Ома")
        db.update_lab(lab_id, subject="Физика", deadline="01.12.2026",
                      description="Проверить зависимость U от I.",
                      x_name="Ток I", x_unit="А", y_name="Напряжение U", y_unit="В",
                      conclusion="Зависимость линейна, закон Ома подтверждён.")
        db.add_step(lab_id, "Собрать схему")
        db.add_step(lab_id, "Снять показания")
        db.toggle_step(db.list_steps(lab_id)[0]["id"])
        assert db.progress(lab_id) == (1, 2)
        db.add_measurements(lab_id, [(0.1, 0.52), (0.2, 0.98), (0.3, 1.55),
                                     (0.4, 2.01), (0.5, 2.48)])
        assert len(db.list_measurements(lab_id)) == 5

        data = collect(db, lab_id)
        out_docx, out_pdf = os.path.join(tmp, "r.docx"), os.path.join(tmp, "r.pdf")
        export_docx(data, out_docx)
        export_pdf(data, out_pdf)
        assert os.path.getsize(out_docx) > 5000 and os.path.getsize(out_pdf) > 5000

        db.delete_lab(lab_id)  # каскадное удаление
        assert not db.list_steps(lab_id) and not db.list_measurements(lab_id)
        db.close()

        # сохранить примеры отчётов для просмотра, если указана папка
        sample = os.environ.get("LABTRACK_SAMPLE_DIR")
        if sample:
            import shutil
            shutil.copy(out_docx, os.path.join(sample, "sample.docx"))
            shutil.copy(out_pdf, os.path.join(sample, "sample.pdf"))
    print("Все проверки пройдены")


if __name__ == "__main__":
    main()
