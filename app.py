from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
import random
import smtplib
from email.message import EmailMessage
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "clave_secreta_para_proyecto_tareas"

DB_NAME = "tareas.db"
DESARROLLADOR = "SEBASTIAN LOPEZ"

SOPORTE_EMAIL = "studytasksoporte@gmail.com"
SOPORTE_PASSWORD = "rbon gbmu gtuh aper"


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def enviar_pin(destino, pin):
    try:
        msg = EmailMessage()
        msg["Subject"] = "PIN de recuperación - StudySoft"
        msg["From"] = SOPORTE_EMAIL
        msg["To"] = destino
        msg.set_content(f"""
Hola.

Tu PIN de recuperación es: {pin}

Este PIN vence en 10 minutos.

StudySoft
Desarrollado por {DESARROLLADOR}
""")

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(SOPORTE_EMAIL, SOPORTE_PASSWORD)
            smtp.send_message(msg)

        return True
    except Exception as e:
        print("ERROR CORREO:", e)
        return False


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
            titulo TEXT NOT NULL,
            descripcion TEXT,
            materia TEXT NOT NULL,
            fecha_entrega TEXT,
            estado TEXT DEFAULT 'Pendiente',
            fecha_creacion TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "usuario" not in session:
            flash("Primero debes iniciar sesión.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


@app.context_processor
def variables_globales():
    return dict(desarrollador=DESARROLLADOR)


@app.route("/")
def inicio():
    return render_template("inicio.html")


@app.route("/login-google")
def login_google():
    flash("El inicio con Google todavía no está configurado.", "info")
    return redirect(url_for("login"))


@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        usuario = request.form["usuario"]
        email = request.form["email"]
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
        usuario = request.form["usuario"]
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM usuarios WHERE usuario = ?",
            (usuario,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["usuario"] = usuario
            flash("Inicio de sesión correcto.", "success")
            return redirect(url_for("listar_tareas"))
        else:
            flash("Usuario o contraseña incorrectos.", "danger")

    return render_template("login.html")


@app.route("/recuperar", methods=["GET", "POST"])
def recuperar():
    if request.method == "POST":
        email = request.form["email"]

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
                conn.close()
                return redirect(url_for("nueva_password"))
            else:
                flash("No se pudo enviar el correo.", "danger")
                print("PIN DE PRUEBA:", pin)
        else:
            flash("No existe una cuenta con ese correo.", "danger")

        conn.close()

    return render_template("recuperar.html")


@app.route("/nueva-password", methods=["GET", "POST"])
def nueva_password():
    if request.method == "POST":
        email = request.form["email"]
        pin = request.form["pin"]
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


@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada correctamente.", "info")
    return redirect(url_for("inicio"))


@app.route("/tareas")
@login_required
def listar_tareas():
    materia = request.args.get("materia", "")
    estado = request.args.get("estado", "")
    fecha = request.args.get("fecha", "")

    query = "SELECT * FROM tareas WHERE 1=1"
    params = []

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

    return render_template(
        "tareas.html",
        tareas=tareas,
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
            (titulo, descripcion, materia, fecha_entrega, estado, fecha_creacion)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
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
    tarea = conn.execute("SELECT * FROM tareas WHERE id = ?", (id,)).fetchone()

    if tarea is None:
        conn.close()
        flash("La tarea no existe.", "danger")
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
            WHERE id = ?
        """, (titulo, descripcion, materia, fecha_entrega, estado, id))
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
    conn.execute("UPDATE tareas SET estado = ? WHERE id = ?", ("Completada", id))
    conn.commit()
    conn.close()

    flash("Tarea marcada como completada.", "success")
    return redirect(url_for("listar_tareas"))


@app.route("/eliminar/<int:id>")
@login_required
def eliminar_tarea(id):
    conn = get_db()
    conn.execute("DELETE FROM tareas WHERE id = ?", (id,))
    conn.commit()
    conn.close()

    flash("Tarea eliminada correctamente.", "danger")
    return redirect(url_for("listar_tareas"))


@app.route("/estadisticas")
@login_required
def estadisticas():
    conn = get_db()

    total = conn.execute("SELECT COUNT(*) AS total FROM tareas").fetchone()["total"]
    pendientes = conn.execute("SELECT COUNT(*) AS total FROM tareas WHERE estado = 'Pendiente'").fetchone()["total"]
    completadas = conn.execute("SELECT COUNT(*) AS total FROM tareas WHERE estado = 'Completada'").fetchone()["total"]
    en_proceso = conn.execute("SELECT COUNT(*) AS total FROM tareas WHERE estado = 'En proceso'").fetchone()["total"]

    por_materia = conn.execute("""
        SELECT materia, COUNT(*) AS cantidad
        FROM tareas
        GROUP BY materia
        ORDER BY cantidad DESC
    """).fetchall()

    conn.close()

    return render_template(
        "estadisticas.html",
        total=total,
        pendientes=pendientes,
        completadas=completadas,
        en_proceso=en_proceso,
        por_materia=por_materia
    )


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)