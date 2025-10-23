# chekcall

Script en Python para validar una lista de teléfonos usando MicroSIP.

## Requisitos

- Windows con [MicroSIP](https://www.microsip.org/downloads) instalado.
- Python 3.10 o superior.
- Acceso al archivo de log de MicroSIP (normalmente en `%APPDATA%\MicroSIP\microsip.log`).

## Instalación

1. Clona este repositorio o copia los archivos en una carpeta local.
2. Crea y activa un entorno virtual (opcional pero recomendado).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
```

No se requiere instalar dependencias adicionales: el script utiliza solo la biblioteca estándar de Python.

## Uso

1. Prepara un archivo CSV con los números a validar. El script usará la primera columna por defecto.
2. Ejecuta el script proporcionando la ruta al CSV:

```powershell
python check_numbers.py numeros.csv --output resultados.csv
```

### Opciones principales

- `--column`: nombre o índice (empezando en 0) de la columna que contiene el número.
- `--microsip`: ruta completa al ejecutable `microsip.exe` si no está en la ubicación predeterminada.
- `--log-file`: ruta al log de MicroSIP si cambiaste la carpeta por defecto.
- `--sip-prefix`: prefijo a anteponer a cada número (ej. `sip:`).
- `--wait`: segundos que se espera antes de colgar la llamada.
- `--timeout`: tiempo máximo para encontrar el resultado en el log.

Al finalizar, el script mostrará un resumen en pantalla. Si se especifica `--output`, también generará un CSV con las columnas `number`, `status` y `details`.

## Limitaciones

- El script depende de que MicroSIP registre el estado de la llamada en su archivo de log.
- No puede garantizar que el tono de marcado corresponda a una conexión real si el proveedor VoIP no entrega información precisa en el log.
- La detección de éxito o fallo se basa en palabras clave (`established`, `connected`, `failed`, etc.). Si tu log utiliza otros términos, ajusta las listas `SUCCESS_KEYWORDS` y `FAILURE_KEYWORDS` dentro del script.

## Licencia

Este proyecto se distribuye bajo la licencia MIT. Consulta el archivo `LICENSE` si decides añadir uno.
