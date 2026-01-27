#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
from dotenv import load_dotenv

# Garante que o root esteja no path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)

from main import SistemaPonto


def main():
    load_dotenv(override=True)
    sistema = None
    try:
        sistema = SistemaPonto()
        sistema.registrar_ponto_automatico()
    finally:
        if sistema:
            sistema.encerrar_sistema()


if __name__ == "__main__":
    main()
