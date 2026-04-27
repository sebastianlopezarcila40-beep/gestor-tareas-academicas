from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
import random
import smtplib
import os
from email.message import EmailMessage
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "clave_secreta_para_proyecto_tareas")

DB_NAME = "tareas.db"
DESARROLLADOR = "SEBASTIAN LOPEZ"
VERSION = "4.03"

SOPORTE_EMAIL = os.getenv("SOPORTE_EMAIL", "studytasksoporte@gmail.com")
SOPORTE_PASSWORD = os.getenv("rbon gbmu gtuh aper", "")
SOPORTE_WHATSAPP = "+57 3126285480"
NOMBRE_IA = "StudyNova IA"


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def agregar_columna_si_no_existe(cur, tabla, columna, definicion):
    columnas = [c["name"] for c in cur.execute(f"PRAGMA table_info({tabla})").fetchall()]
    if columna not in columnas:
        cur.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion}")


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL UNIQUE,
            email TEXT UNIQUE,
            password TEXT NOT NULL,
            reset_pin TEXT,
            reset_expira TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tareas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            titulo TEXT NOT NULL,
            descripcion TEXT,
            materia TEXT NOT NULL,
            fecha_entrega TEXT,
            estado TEXT DEFAULT 'Pendiente',
            fecha_creacion TEXT NOT NULL
        )
    """)

    agregar_columna_si_no_existe(cur, "usuarios", "email", "TEXT")
    agregar_columna_si_no_existe(cur, "usuarios", "reset_pin", "TEXT")
    agregar_columna_si_no_existe(cur, "usuarios", "reset_expira", "TEXT")
    agregar_columna_si_no_existe(cur, "tareas", "usuario_id", "INTEGER")

    cur.execute("SELECT * FROM usuarios WHERE usuario = ?", ("admin",))
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO usuarios (usuario, email, password) VALUES (?, ?, ?)",
            ("admin", "admin@studytask.com", generate_password_hash("1234"))
        )

    conn.commit()
    conn.close()


def enviar_pin(destino, pin):
    if not SOPORTE_PASSWORD:
        print("ERROR CORREO: falta configurar SOPORTE_PASSWORD en Render")
        print("PIN DE PRUEBA:", pin)
        return False

    try:
        msg = EmailMessage()
        msg["Subject"] = "PIN de recuperación - StudySoft"
        msg["From"] = SOPORTE_EMAIL
        msg["To"] = destino
        msg.set_content(f"""
Hola.

Tu PIN de recuperación es: {pin}

Este PIN vence en 10 minutos.

StudySoft v{VERSION}
Soporte: {SOPORTE_EMAIL}
WhatsApp: {SOPORTE_WHATSAPP}
Desarrollado por {DESARROLLADOR}
""")

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(SOPORTE_EMAIL, SOPORTE_PASSWORD)
            smtp.send_message(msg)

        return True
    except Exception as e:
        print("ERROR CORREO:", e)
        print("PIN DE PRUEBA:", pin)
        return False


def usuario_actual_id():
    return session.get("usuario_id")


def analizar_tarea_ia(tarea):
    titulo = tarea["titulo"].lower()
    descripcion = (tarea["descripcion"] or "").lower()
    materia = tarea["materia"].lower()
    fecha_entrega = tarea["fecha_entrega"]

    texto = f"{titulo} {descripcion} {materia}"

    prioridad = "Media"
    consejo = "Organiza un bloque de estudio y avanza por partes."

    if "examen" in texto or "evaluación" in texto or "quiz" in texto:
        prioridad = "Alta"
        consejo = "Prepárate con anticipación. Estudia mínimo 30 minutos hoy y haz un repaso antes de la fecha."

    if "mañana" in texto or "urgente" in texto:
        prioridad = "Alta"
        consejo = "Haz esta tarea primero. Evita dejarla para última hora."

    if fecha_entrega:
        try:
            fecha = datetime.strptime(fecha_entrega, "%Y-%m-%d").date()
            hoy = datetime.now().date()
            dias = (fecha - hoy).days

            if dias <= 1:
                prioridad = "Alta"
                consejo = "La fecha está muy cerca. Prioriza esta tarea hoy."
            elif dias <= 3 and prioridad != "Alta":
                prioridad = "Media"
                consejo = "Empieza pronto para no acumular trabajo."
            elif dias >= 7:
                prioridad = "Baja"
                consejo = "Aún tienes tiempo, pero agenda un avance pequeño."
        except:
            pass

    return {
        "nombre_ia": NOMBRE_IA,
        "prioridad": prioridad,
        "consejo": consejo
    }


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "usuario" not in session or "usuario_id" not in session:
            flash("Primero debes iniciar sesión.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


@app.context_processor
def variables_globales():
    return dict(
        desarrollador=DESARROLLADOR,
        version=VERSION,
        soporte_email=SOPORTE_EMAIL,
        soporte_whatsapp=SOPORTE_WHATSAPP,
        nombre_ia=NOMBRE_IA,
        cookies_aceptadas=request.cookies.get("cookies_aceptadas") == "si",
        aviso_version=f"🚀 Nueva versión {VERSION}: StudyNova IA, cookies, soporte visible y mejoras de experiencia."
    )


@app.route("/")
def inicio():
    return render_template("inicio.html")


@app.route("/aceptar-cookies")
def aceptar_cookies():
    respuesta = make_response(redirect(request.referrer or url_for("inicio")))
    respuesta.set_cookie("cookies_aceptadas", "si", max_age=60 * 60 * 24 * 365)
    return respuesta


@app.route("/login-google")
def login_google():
    flash("El inicio con Google estará disponible en una próxima actualización.", "info")
    return redirect(url_for("login"))


@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        usuario = request.form["usuario"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO usuarios (usuario, email, password) VALUES (?, ?, ?)",
                (usuario, email, generate_password_hash(password))
            )
            conn.commit()
            flash("Cuenta creada correctamente.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Ese usuario o correo ya existe.", "danger")
        finally:
            conn.close()

    return render_template("registro.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"].strip()
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM usuarios WHERE usuario = ?",
            (usuario,)
        ).fetchone()

        if user and check_password_hash(user["password"], password):
            session["usuario"] = user["usuario"]
            session["usuario_id"] = user["id"]
            flash("Inicio de sesión correcto.", "success")
            conn.close()
            return redirect(url_for("listar_tareas"))

        conn.close()
        flash("Usuario o contraseña incorrectos.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada correctamente.", "info")
    return redirect(url_for("inicio"))


@app.route("/recuperar", methods=["GET", "POST"])
def recuperar():
    if request.method == "POST":
        email = request.form["email"].strip().lower()

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM usuarios WHERE email = ?",
            (email,)
        ).fetchone()

        if user:
            pin = str(random.randint(100000, 999999))
            expira = (datetime.now() + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")

            conn.execute(
                "UPDATE usuarios SET reset_pin = ?, reset_expira = ? WHERE email = ?",
                (pin, expira, email)
            )
            conn.commit()

            enviado = enviar_pin(email, pin)

            if enviado:
                flash("Te enviamos un PIN al correo registrado.", "success")
            else:
                flash("No se pudo enviar el correo. Revisa la configuración.", "danger")

            conn.close()
            return redirect(url_for("nueva_password"))

        flash("No existe una cuenta con ese correo.", "danger")
        conn.close()

    return render_template("recuperar.html")


@app.route("/nueva-password", methods=["GET", "POST"])
def nueva_password():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        pin = request.form["pin"].strip()
        nueva = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM usuarios WHERE email = ? AND reset_pin = ?",
            (email, pin)
        ).fetchone()

        if not user:
            conn.close()
            flash("PIN incorrecto.", "danger")
            return redirect(url_for("nueva_password"))

        if not user["reset_expira"]:
            conn.close()
            flash("Solicita un nuevo PIN.", "danger")
            return redirect(url_for("recuperar"))

        expira = datetime.strptime(user["reset_expira"], "%Y-%m-%d %H:%M:%S")

        if datetime.now() > expira:
            conn.close()
            flash("El PIN venció. Solicita uno nuevo.", "danger")
            return redirect(url_for("recuperar"))

        conn.execute(
            "UPDATE usuarios SET password = ?, reset_pin = NULL, reset_expira = NULL WHERE email = ?",
            (generate_password_hash(nueva), email)
        )
        conn.commit()
        conn.close()

        flash("Contraseña actualizada correctamente.", "success")
        return redirect(url_for("login"))

    return render_template("nueva_password.html")


@app.route("/tareas")
@login_required
def listar_tareas():
    materia = request.args.get("materia", "")
    estado = request.args.get("estado", "")
    fecha = request.args.get("fecha", "")

    query = "SELECT * FROM tareas WHERE usuario_id = ?"
    params = [usuario_actual_id()]

    if materia:
        query += " AND materia LIKE ?"
        params.append(f"%{materia}%")

    if estado:
        query += " AND estado = ?"
        params.append(estado)

    if fecha:
        query += " AND fecha_entrega = ?"
        params.append(fecha)

    query += " ORDER BY fecha_entrega ASC"

    conn = get_db()
    tareas = conn.execute(query, params).fetchall()
    conn.close()

    tareas_con_ia = []
    for tarea in tareas:
        tareas_con_ia.append({
            "tarea": tarea,
            "ia": analizar_tarea_ia(tarea)
        })

    return render_template(
        "tareas.html",
        tareas=tareas,
        tareas_con_ia=tareas_con_ia,
        materia=materia,
        estado=estado,
        fecha=fecha
    )


@app.route("/crear", methods=["GET", "POST"])
@login_required
def crear_tarea():
    if request.method == "POST":
        titulo = request.form["titulo"]
        descripcion = request.form["descripcion"]
        materia = request.form["materia"]
        fecha_entrega = request.form["fecha_entrega"]

        conn = get_db()
        conn.execute("""
            INSERT INTO tareas 
            (usuario_id, titulo, descripcion, materia, fecha_entrega, estado, fecha_creacion)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            usuario_actual_id(),
            titulo,
            descripcion,
            materia,
            fecha_entrega,
            "Pendiente",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
        conn.close()

        flash("Tarea creada correctamente.", "success")
        return redirect(url_for("listar_tareas"))

    return render_template("crear.html")


@app.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_tarea(id):
    conn = get_db()
    tarea = conn.execute(
        "SELECT * FROM tareas WHERE id = ? AND usuario_id = ?",
        (id, usuario_actual_id())
    ).fetchone()

    if tarea is None:
        conn.close()
        flash("La tarea no existe o no pertenece a tu cuenta.", "danger")
        return redirect(url_for("listar_tareas"))

    if request.method == "POST":
        titulo = request.form["titulo"]
        descripcion = request.form["descripcion"]
        materia = request.form["materia"]
        fecha_entrega = request.form["fecha_entrega"]
        estado = request.form["estado"]

        conn.execute("""
            UPDATE tareas
            SET titulo = ?, descripcion = ?, materia = ?, fecha_entrega = ?, estado = ?
            WHERE id = ? AND usuario_id = ?
        """, (
            titulo,
            descripcion,
            materia,
            fecha_entrega,
            estado,
            id,
            usuario_actual_id()
        ))
        conn.commit()
        conn.close()

        flash("Tarea actualizada correctamente.", "success")
        return redirect(url_for("listar_tareas"))

    conn.close()
    return render_template("editar.html", tarea=tarea)


@app.route("/completar/<int:id>")
@login_required
def completar_tarea(id):
    conn = get_db()
    conn.execute(
        "UPDATE tareas SET estado = ? WHERE id = ? AND usuario_id = ?",
        ("Completada", id, usuario_actual_id())
    )
    conn.commit()
    conn.close()

    flash("Tarea marcada como completada.", "success")
    return redirect(url_for("listar_tareas"))


@app.route("/eliminar/<int:id>")
@login_required
def eliminar_tarea(id):
    conn = get_db()
    conn.execute(
        "DELETE FROM tareas WHERE id = ? AND usuario_id = ?",
        (id, usuario_actual_id())
    )
    conn.commit()
    conn.close()

    flash("Tarea eliminada correctamente.", "danger")
    return redirect(url_for("listar_tareas"))


@app.route("/estadisticas")
@login_required
def estadisticas():
    conn = get_db()
    uid = usuario_actual_id()

    total = conn.execute(
        "SELECT COUNT(*) AS total FROM tareas WHERE usuario_id = ?",
        (uid,)
    ).fetchone()["total"]

    pendientes = conn.execute(
        "SELECT COUNT(*) AS total FROM tareas WHERE estado = 'Pendiente' AND usuario_id = ?",
        (uid,)
    ).fetchone()["total"]

    completadas = conn.execute(
        "SELECT COUNT(*) AS total FROM tareas WHERE estado = 'Completada' AND usuario_id = ?",
        (uid,)
    ).fetchone()["total"]

    en_proceso = conn.execute(
        "SELECT COUNT(*) AS total FROM tareas WHERE estado = 'En proceso' AND usuario_id = ?",
        (uid,)
    ).fetchone()["total"]

    por_materia = conn.execute("""
        SELECT materia, COUNT(*) AS cantidad
        FROM tareas
        WHERE usuario_id = ?
        GROUP BY materia
        ORDER BY cantidad DESC
    """, (uid,)).fetchall()

    conn.close()

    return render_template(
        "estadisticas.html",
        total=total,
        pendientes=pendientes,
        completadas=completadas,
        en_proceso=en_proceso,
        por_materia=por_materia
    )


init_db()

if __name__ == "__main__":
    app.run(debug=True)