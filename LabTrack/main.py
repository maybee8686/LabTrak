"""Точка входа LabTrack: python main.py"""
from db import Database
from ui import App


def main():
    db = Database()
    try:
        App(db).mainloop()
    finally:
        db.close()


if __name__ == "__main__":
    main()
