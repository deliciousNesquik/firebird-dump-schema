"""Точка входа для PyInstaller — собирает CLI в самодостаточный бинарь.

Бинарю Python не нужен; нужен лишь установленный клиент Firebird (`libfbclient`),
который `firebird-driver` грузит в рантайме (см. README).
"""

import sys

from fbschema.cli import main

if __name__ == "__main__":
    sys.exit(main())
