import logging
from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, auth, db
import requests
import datetime
import json
import os

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

logger.info("Inicializando Firebase...")
firebase_config = json.loads(os.environ["GOOGLE_APPLICATION_CREDENTIALS_JSON"])
cred = credentials.Certificate(firebase_config)
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://tfgjuegofisica-default-rtdb.europe-west1.firebasedatabase.app'
})

FIREBASE_API_KEY = "AIzaSyDo9JLMIz5lmvVqZlFFw4tc7E92EYzXCn0"

# --- AUTENTICACIÓN ---
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    logger.info(f"POST /login - Datos recibidos: {data}")
    payload = {
        "email": data.get("email"),
        "password": data.get("password"),
        "returnSecureToken": True
    }
    res = requests.post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}",
        json=payload
    )
    logger.info(f"Respuesta de Firebase Auth: {res.status_code} - {res.text}")
    if res.status_code == 200:
        return jsonify(res.json())
    else:
        return jsonify({"error": res.json()}), 401

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    logger.info(f"POST /register - Datos recibidos: {data}")
    try:
        user = auth.create_user(
            email=data["email"],
            password=data["password"],
            display_name=data["nombre"]
        )
        db.reference(f"usuarios/{user.uid}").set({
            "nombre": data["nombre"],
            "email": data["email"],
            "clases": {}
        })
        logger.info(f"Usuario creado: {user.uid}")
        return jsonify({"uid": user.uid})
    except Exception as e:
        logger.error(f"Error al registrar usuario: {e}")
        return jsonify({"error": str(e)}), 400

# --- USUARIOS ---
@app.route("/usuario/<uid>", methods=["GET"])
def obtener_usuario(uid):
    logger.info(f"GET /usuario/{uid}")
    usuario = db.reference(f"usuarios/{uid}").get()
    if usuario:
        logger.info(f"Usuario encontrado: {usuario}")
        return jsonify(usuario)
    else:
        logger.warning(f"Usuario no encontrado: {uid}")
        return jsonify({"error": "Usuario no encontrado"}), 404

@app.route("/usuario/<uid>", methods=["PUT"])
def actualizar_usuario(uid):
    data = request.json
    logger.info(f"PUT /usuario/{uid} - Datos: {data}")
    db.reference(f"usuarios/{uid}").update(data)
    return jsonify({"ok": True})

@app.route("/usuario/<uid>", methods=["DELETE"])
def eliminar_usuario(uid):
    logger.info(f"DELETE /usuario/{uid}")
    try:
        auth.delete_user(uid)
        db.reference(f"usuarios/{uid}").delete()
        logger.info(f"Usuario eliminado: {uid}")
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"Error al eliminar usuario: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/usuario/<uid>/clases", methods=["GET"])
def obtener_clases(uid):
    logger.info(f"GET /usuario/{uid}/clases")
    clases_ids = db.reference(f"usuarios/{uid}/clases").get()
    clases_info = {}
    if clases_ids:
        for clase_id in clases_ids:
            clase = db.reference(f"clases/{clase_id}").get()
            if clase:
                clases_info[clase_id] = clase
    logger.info(f"Clases encontradas: {list(clases_info.keys())}")
    return jsonify(clases_info)

# --- CLASES ---
@app.route("/clase", methods=["POST"])
def crear_clase():
    data = request.json
    logger.info(f"POST /clase - Datos: {data}")
    codigo = data["codigo"]
    clase_ref = db.reference(f"clases/{codigo}")
    clase_ref.set({
        "nombre": data["nombre"],
        "creadorEmail": data["creadorEmail"],
        "codigo": codigo,
        "usuarios": {data["uidCreador"]: True},
        "problemas": {}
    })
    db.reference(f"usuarios/{data['uidCreador']}/clases/{codigo}").set(True)
    logger.info(f"Clase creada: {codigo}")
    return jsonify({"ok": True, "codigo": codigo})

@app.route("/clase/<codigo>", methods=["GET"])
def obtener_clase(codigo):
    logger.info(f"GET /clase/{codigo}")
    ref = db.reference(f"clases/{codigo}").get()
    if ref:
        logger.info(f"Clase encontrada: {codigo}")
        return jsonify(ref)
    else:
        logger.warning(f"Clase no existe: {codigo}")
        return jsonify({"error": "No existe"}), 404

@app.route("/clase/<codigo>", methods=["DELETE"])
def borrar_clase(codigo):
    logger.info(f"DELETE /clase/{codigo}")
    db.reference(f"clases/{codigo}").delete()
    logger.info(f"Clase eliminada: {codigo}")
    return jsonify({"ok": True})

@app.route("/clase/<codigo_clase>/unir", methods=["POST"])
def unir_a_clase(codigo_clase):
    data = request.json
    uid = data.get("uid")
    logger.info(f"POST /clase/{codigo_clase}/unir - UID: {uid}")
    if not uid:
        logger.warning("UID requerido para unirse a clase")
        return jsonify({"error": "uid requerido"}), 400
    db.reference(f"clases/{codigo_clase}/usuarios/{uid}").set(True)
    db.reference(f"usuarios/{uid}/clases/{codigo_clase}").set(True)
    logger.info(f"Usuario {uid} unido a clase {codigo_clase}")
    return jsonify({"ok": True})

@app.route("/clase/<codigo>/salir", methods=["POST"])
def salir_de_clase(codigo):
    data = request.json
    uid = data.get("uid")
    logger.info(f"POST /clase/{codigo}/salir - UID: {uid}")
    if not uid:
        logger.warning("UID requerido para salir de clase")
        return jsonify({"error": "uid requerido"}), 400
    db.reference(f"clases/{codigo}/usuarios/{uid}").delete()
    db.reference(f"usuarios/{uid}/clases/{codigo}").delete()
    logger.info(f"Usuario {uid} salió de clase {codigo}")
    return jsonify({"ok": True})

@app.route("/clase/<codigo>/usuarios", methods=["GET"])
def obtener_usuarios_clase(codigo):
    logger.info(f"GET /clase/{codigo}/usuarios")
    usuarios = db.reference(f"clases/{codigo}/usuarios").get()
    lista_usuarios = []
    if usuarios:
        for uid in usuarios:
            datos = db.reference(f"usuarios/{uid}").get()
            if datos:
                lista_usuarios.append({"uid": uid, "nombre": datos.get("nombre", "")})
    logger.info(f"Usuarios en clase {codigo}: {lista_usuarios}")
    return jsonify(lista_usuarios)

# --- PROBLEMAS ---
@app.route("/clase/<codigo>/problemas", methods=["POST"])
def subir_problema(codigo):
    data = request.json
    logger.info(f"POST /clase/{codigo}/problemas - Datos: {data}")
    problema_id = data.get("idProblema", f"problema_{int(datetime.datetime.utcnow().timestamp() * 1000)}")
    problema = {
        "tipo": data.get("tipo"),
        "datosConfiguracion": data.get("datosConfiguracion"),
        "fechaCreacion": datetime.datetime.utcnow().isoformat()
    }
    db.reference(f"clases/{codigo}/problemas/{problema_id}").set(problema)
    logger.info(f"Problema subido: {problema_id} en clase {codigo}")
    return jsonify({"ok": True, "problemaId": problema_id})

@app.route("/clase/<codigo>/problemas", methods=["GET"])
def obtener_problemas(codigo):
    logger.info(f"GET /clase/{codigo}/problemas")
    problemas = db.reference(f"clases/{codigo}/problemas").get()
    logger.info(f"Problemas encontrados: {list(problemas.keys()) if problemas else []}")
    return jsonify(problemas or {})

@app.route("/clase/<codigo>/problemas/<pid>", methods=["DELETE"])
def borrar_problema(codigo, pid):
    logger.info(f"DELETE /clase/{codigo}/problemas/{pid}")
    db.reference(f"clases/{codigo}/problemas/{pid}").delete()
    logger.info(f"Problema eliminado: {pid} de clase {codigo}")
    return jsonify({"ok": True})

@app.route("/clase/<codigo>/problemas/<pid>", methods=["PUT"])
def editar_problema(codigo, pid):
    data = request.json
    logger.info(f"PUT /clase/{codigo}/problemas/{pid} - Datos: {data}")
    db.reference(f"clases/{codigo}/problemas/{pid}").update(data)
    logger.info(f"Problema editado: {pid} en clase {codigo}")
    return jsonify({"ok": True})

# --- SERVIDOR PARA PRODUCCIÓN ---
from waitress import serve

if __name__ == "__main__":
    logger.info("Iniciando servidor en 0.0.0.0:8080")
    serve(app, host="0.0.0.0", port=8080)