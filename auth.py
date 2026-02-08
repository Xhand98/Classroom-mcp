#!/usr/bin/env python3
"""
Script de autorización para Google Classroom MCP Server
Ejecuta el flujo de OAuth y guarda el token
"""

import os
import sys
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.student-submissions.me.readonly"
]

def main():
    print("╔════════════════════════════════════════════════════════════╗")
    print("║  🔐 Autorización de Google Classroom                      ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    
    # Verificar si ya existe un token válido
    if os.path.exists("token.json"):
        print("📄 Token existente encontrado. Verificando...")
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        
        if creds.valid:
            print("✅ El token actual es válido")
            print()
            response = input("¿Deseas renovar la autorización de todos modos? (s/N): ").strip().lower()
            if response not in ['s', 'si', 'sí', 'y', 'yes']:
                print("✅ Usando token existente")
                return 0
        elif creds.expired and creds.refresh_token:
            print("🔄 Token expirado. Intentando refrescar...")
            try:
                creds.refresh(Request())
                with open("token.json", "w") as token:
                    token.write(creds.to_json())
                print("✅ Token refrescado exitosamente")
                return 0
            except Exception as e:
                print(f"⚠️  No se pudo refrescar: {e}")
                print("Iniciando nueva autorización...")
    
    # Verificar que existe credentials.json
    if not os.path.exists("credentials.json"):
        print("❌ Error: No se encontró 'credentials.json'")
        print()
        print("Este archivo contiene las credenciales OAuth de Google.")
        print("Asegúrate de que existe en el directorio actual.")
        return 1
    
    print()
    print("📋 PASOS A SEGUIR:")
    print("  1. Se abrirá una URL de autorización")
    print("  2. Visita esa URL en tu navegador")
    print("  3. Inicia sesión con tu cuenta de Google")
    print("  4. Autoriza el acceso a Google Classroom")
    print("  5. Copia el código que te proporcionan")
    print("  6. Pégalo aquí")
    print()
    
    input("Presiona ENTER para continuar...")
    print()
    
    try:
        # Iniciar flujo de autorización
        flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
        
        print("🔐 Generando URL de autorización...")
        
        # Configurar redirect_uri explícitamente
        flow.redirect_uri = flow.client_config.get('redirect_uris', ['http://localhost'])[0]
        
        # Generar URL de autorización con todos los parámetros necesarios
        auth_url, _ = flow.authorization_url(
            prompt="consent",
            access_type='offline',
            include_granted_scopes='true'
        )
        
        print()
        print("╔════════════════════════════════════════════════════════════╗")
        print("║  📋 URL DE AUTORIZACIÓN                                    ║")
        print("╚════════════════════════════════════════════════════════════╝")
        print()
        print(auth_url)
        print()
        print("Copia y pega esta URL en tu navegador.")
        print()
        
        # Solicitar código
        code = input("🔑 Pega aquí el código de autorización: ").strip()
        
        if not code:
            print("❌ No se proporcionó ningún código")
            return 1
        
        print()
        print("⏳ Validando código...")
        
        # Obtener credenciales con el código
        flow.fetch_token(code=code)
        creds = flow.credentials
        
        # Guardar token
        with open("token.json", "w") as token:
            token.write(creds.to_json())
        
        print("✅ Autorización exitosa!")
        print()
        print("╔════════════════════════════════════════════════════════════╗")
        print("║  ✅ AUTORIZACIÓN COMPLETADA                               ║")
        print("╚════════════════════════════════════════════════════════════╝")
        print()
        print("El token se guardó en: token.json")
        print()
        print("Ahora puedes ejecutar:")
        print("  • Servidor: ./run_server.sh")
        print("  • Cliente:  ./run_client.sh")
        print()
        
        return 0
        
    except Exception as e:
        print()
        print("╔════════════════════════════════════════════════════════════╗")
        print("║  ❌ ERROR DURANTE LA AUTORIZACIÓN                         ║")
        print("╚════════════════════════════════════════════════════════════╝")
        print()
        print(f"Error: {e}")
        print()
        
        # Mensajes de ayuda según el error
        error_str = str(e).lower()
        if "invalid_grant" in error_str or "malformed" in error_str:
            print("💡 El código proporcionado no es válido.")
            print("   Asegúrate de copiar el código completo sin espacios extra.")
        elif "redirect_uri" in error_str:
            print("💡 Error de configuración en credentials.json")
        elif "credentials" in error_str or "client" in error_str:
            print("💡 Verifica que credentials.json sea válido")
        
        print()
        print("Puedes intentar nuevamente ejecutando:")
        print("  .venv/bin/python auth.py")
        print()
        
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print()
        print()
        print("⚠️  Autorización cancelada por el usuario")
        sys.exit(1)
    except Exception as e:
        print()
        print(f"❌ Error inesperado: {e}")
        sys.exit(1)
