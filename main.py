from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, auth, db
import requests
import datetime
import json
import os

app = Flask(__name__)

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
    payload = {
        "email": data.get("email"),
        "password": data.get("password"),
        "returnSecureToken": True
    }
    res = requests.post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}",
        json=payload
    )
    if res.status_code == 200:
        return jsonify(res.json())
    else:
        return jsonify({"error": res.json()}), 401

@app.route("/register", methods=["POST"])
def register():
    data = request.json
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
        return jsonify({"uid": user.uid})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# --- USUARIOS ---
@app.route("/usuario/<uid>", methods=["GET"])
def obtener_usuario(uid):
    usuario = db.reference(f"usuarios/{uid}").get()
    if usuario:
        return jsonify(usuario)
    else:
        return jsonify({"error": "Usuario no encontrado"}), 404

@app.route("/usuario/<uid>", methods=["PUT"])
def actualizar_usuario(uid):
    data = request.json
    db.reference(f"usuarios/{uid}").update(data)
    return jsonify({"ok": True})

@app.route("/usuario/<uid>", methods=["DELETE"])
def eliminar_usuario(uid):
    try:
        auth.delete_user(uid)
        db.reference(f"usuarios/{uid}").delete()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/usuario/<uid>/clases", methods=["GET"])
def obtener_clases(uid):
    clases_ids = db.reference(f"usuarios/{uid}/clases").get()
    clases_info = {}
    if clases_ids:
        for clase_id in clases_ids:
            clase = db.reference(f"clases/{clase_id}").get()
            if clase:
                clases_info[clase_id] = clase
    return jsonify(clases_info)

# --- CLASES ---
@app.route("/clase", methods=["POST"])
def crear_clase():
    data = request.json
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
    return jsonify({"ok": True, "codigo": codigo})

@app.route("/clase/<codigo>", methods=["GET"])
def obtener_clase(codigo):
    ref = db.reference(f"clases/{codigo}").get()
    if ref:
        return jsonify(ref)
    else:
        return jsonify({"error": "No existe"}), 404

@app.route("/clase/<codigo>", methods=["DELETE"])
def borrar_clase(codigo):
    db.reference(f"clases/{codigo}").delete()
    return jsonify({"ok": True})

@app.route("/clase/<codigo_clase>/unir", methods=["POST"])
def unir_a_clase(codigo_clase):
    data = request.json
    uid = data.get("uid")
    if not uid:
        return jsonify({"error": "uid requerido"}), 400
    db.reference(f"clases/{codigo_clase}/usuarios/{uid}").set(True)
    db.reference(f"usuarios/{uid}/clases/{codigo_clase}").set(True)
    return jsonify({"ok": True})

@app.route("/clase/<codigo>/salir", methods=["POST"])
def salir_de_clase(codigo):
    data = request.json
    uid = data.get("uid")
    if not uid:
        return jsonify({"error": "uid requerido"}), 400
    db.reference(f"clases/{codigo}/usuarios/{uid}").delete()
    db.reference(f"usuarios/{uid}/clases/{codigo}").delete()
    return jsonify({"ok": True})

@app.route("/clase/<codigo>/usuarios", methods=["GET"])
def obtener_usuarios_clase(codigo):
    usuarios = db.reference(f"clases/{codigo}/usuarios").get()
    lista_usuarios = []
    if usuarios:
        for uid in usuarios:
            datos = db.reference(f"usuarios/{uid}").get()
            if datos:
                lista_usuarios.append({"uid": uid, "nombre": datos.get("nombre", "")})
    return jsonify(lista_usuarios)

# --- PROBLEMAS ---
@app.route("/clase/<codigo>/problemas", methods=["POST"])
def subir_problema(codigo):
    data = request.json
    problema_id = data.get("idProblema", f"problema_{int(datetime.datetime.utcnow().timestamp() * 1000)}")
    problema = {
        "tipo": data.get("tipo"),
        "datosConfiguracion": data.get("datosConfiguracion"),
        "fechaCreacion": datetime.datetime.utcnow().isoformat()
    }
    db.reference(f"clases/{codigo}/problemas/{problema_id}").set(problema)
    return jsonify({"ok": True, "problemaId": problema_id})

@app.route("/clase/<codigo>/problemas", methods=["GET"])
def obtener_problemas(codigo):
    problemas = db.reference(f"clases/{codigo}/problemas").get()
    return jsonify(problemas or {})

@app.route("/clase/<codigo>/problemas/<pid>", methods=["DELETE"])
def borrar_problema(codigo, pid):
    db.reference(f"clases/{codigo}/problemas/{pid}").delete()
    return jsonify({"ok": True})

@app.route("/clase/<codigo>/problemas/<pid>", methods=["PUT"])
def editar_problema(codigo, pid):
    data = request.json
    db.reference(f"clases/{codigo}/problemas/{pid}").update(data)
    return jsonify({"ok": True})

# --- SERVIDOR PARA PRODUCCIÓN ---
from waitress import serve

if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=8080)