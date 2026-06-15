#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script de teste para validar geração de códigos de Gift Cards
"""

import sys
sys.path.insert(0, '/home/ubuntu/syntek_bot')

from main import GiftCardCodeGenerator

def test_code_generation():
    """Testa a geração de códigos"""
    
    print("=" * 60)
    print("TESTE DE GERAÇÃO DE CÓDIGOS DE GIFT CARDS")
    print("=" * 60)
    
    # Teste Shopee
    print("\n🎁 SHOPEE:")
    for i in range(3):
        code = GiftCardCodeGenerator.generate_shopee()
        print(f"   Código {i+1}: {code}")
    
    # Teste iFood
    print("\n🍔 IFOOD:")
    for i in range(3):
        code = GiftCardCodeGenerator.generate_ifood()
        print(f"   Código {i+1}: {code}")
    
    # Teste Steam
    print("\n🎮 STEAM:")
    for i in range(3):
        code = GiftCardCodeGenerator.generate_steam()
        print(f"   Código {i+1}: {code}")
    
    # Teste Google Play
    print("\n🎮 GOOGLE PLAY:")
    for i in range(3):
        code = GiftCardCodeGenerator.generate_google_play()
        print(f"   Código {i+1}: {code}")
    
    print("\n" + "=" * 60)
    print("✅ Teste concluído com sucesso!")
    print("=" * 60)

if __name__ == '__main__':
    test_code_generation()
