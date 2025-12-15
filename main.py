import flet as ft
from flet import Colors, Icons
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import fsolve
import io
import base64

# ====================================================================
# --- CLASE DE ESTADO (SOLUCIÓN AL PROBLEMA DE VARIABLES) ---
# ====================================================================
class SimulationState:
    def __init__(self):
        self.platos = []
        self.x_pot = 0.5
        self.moles_pot = 100.0
        self.step_count = 0
        self.A_params = {}
        self.B_params = {}

# ====================================================================
# --- LÓGICA TERMODINÁMICA ---
# ====================================================================

def get_antoine_params(Tb, P_ref, T_ref=25.0):
    """Calcula los parámetros A y B de Antoine simplificado."""
    T1, P1 = Tb + 273.15, 760.0
    T2, P2 = T_ref + 273.15, P_ref
    try:
        B = -np.log(P1/P2) / (1/T1 - 1/T2)
        A = np.log(P1) + B/T1
        return A, B
    except Exception:
        return 0, 0

def get_Psat(T_kelvin, A, B):
    """Calcula la presión de vapor saturada."""
    return np.exp(A - B/T_kelvin)

def get_T_bub(x_liq, A_A, B_A, A_B, B_B):
    """Calcula T de burbuja (°C) y y_vap (Ley de Raoult)."""
    P_total = 760
    # Mejor estimación inicial para evitar divergencia
    T_guess = (80.1 + 110.6) / 2
    
    def error_func(T_c):
        T_k = T_c + 273.15
        PA = get_Psat(T_k, A_A, B_A)
        PB = get_Psat(T_k, A_B, B_B)
        return P_total - (x_liq * PA + (1-x_liq) * PB)

    try:
        T_res = fsolve(error_func, T_guess)[0]
        T_k = T_res + 273.15
        PA = get_Psat(T_k, A_A, B_A)
        y_vap = (x_liq * PA) / P_total
        return T_res, y_vap
    except:
        return T_guess, x_liq

# ====================================================================
# --- FUNCIÓN PRINCIPAL DE FLET ---
# ====================================================================

def main(page: ft.Page):
    page.title = "Simulador de Destilación (Flet/Render)"
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.scroll = ft.ScrollMode.ADAPTIVE
    
    # --- INSTANCIA DEL ESTADO ---
    # Esto asegura que 'state' sea el mismo objeto para todas las funciones
    state = SimulationState()
    
    # --- INTERFAZ BÁSICA ---
    txt_name_a = ft.TextField(label="Comp. A (Volátil)", value="Benceno", width=150)
    txt_tb_a = ft.TextField(label="Tb A (°C)", value="80.1", width=100)
    txt_p_ref_a = ft.TextField(label="P_vap a 25°C (mmHg)", value="95.0", width=150)
    
    txt_name_b = ft.TextField(label="Comp. B (Menos Volátil)", value="Tolueno", width=150)
    txt_tb_b = ft.TextField(label="Tb B (°C)", value="110.6", width=100)
    txt_p_ref_b = ft.TextField(label="P_vap a 25°C (mmHg)", value="28.0", width=150)
    
    slider_platos = ft.Slider(min=1, max=12, divisions=11, value=5, label="N° Platos: {value}")
    txt_x0 = ft.TextField(label="x_inicial (Fracción Molar)", value="0.5", width=150)
    
    lbl_estado = ft.Text("Estado: Esperando configuración...", color=Colors.BLUE_700)
    lbl_info_top = ft.Text("--", size=18, weight=ft.FontWeight.BOLD, color=Colors.GREEN_700)
    lbl_moles = ft.Text(f"Moles Pot: {state.moles_pot:.1f}", size=14)
    
    col_data_display = ft.Column(scroll=ft.ScrollMode.AUTO, height=300) 
    img_plot = ft.Image(width=500, height=500) # Un poco más grande para ver detalles

    # --- FUNCIONES ---
    
    def dibujar_grafico_matplotlib():
        """Genera el gráfico T-xy basado en el estado actual."""
        # Usamos los datos almacenados en 'state'
        platos_list = state.platos
        A_p = state.A_params
        B_p = state.B_params
        
        plt.clf()
        fig = plt.figure(figsize=(5, 5))
        ax = fig.add_subplot(111)
        
        Tb_A, Tb_B = A_p['Tb'], B_p['Tb']
        AA, BA, AB, BB = A_p['A'], A_p['B'], B_p['A'], B_p['B']
        
        # --- 1. Calcular Curvas de Equilibrio ---
        x_curve, y_curve, T_plot_curve = [], [], []
        T_test = np.linspace(min(Tb_A, Tb_B), max(Tb_A, Tb_B), 100)

        for T in T_test:
            T_k = T + 273.15
            PA, PB = get_Psat(T_k, AA, BA), get_Psat(T_k, AB, BB)
            try:
                x = (760 - PB) / (PA - PB) 
                y = x * PA / 760 
                if 0 <= x <= 1:
                    x_curve.append(x)
                    y_curve.append(y)
                    T_plot_curve.append(T)
            except:
                pass

        # Graficar curvas base
        ax.plot(x_curve, T_plot_curve, 'b-', label='Líquido (Burbuja)', alpha=0.6)
        ax.plot(y_curve, T_plot_curve, 'r-', label='Vapor (Rocío)', alpha=0.6)
        
        # --- 2. Graficar Platos y Escaleras ---
        if platos_list:
            x_vals = [p['x'] for p in platos_list]
            y_vals = [p['y'] for p in platos_list]
            T_vals = [p['T'] for p in platos_list]
            
            # Puntos
            ax.plot(x_vals, T_vals, 'ko', markersize=4, zorder=5) # Líquido
            ax.plot(y_vals, T_vals, 'g^', markersize=4, zorder=5) # Vapor

            # -- Construcción de Escaleras (Stepping) --
            # Para cada plato, dibujamos la línea de equilibrio (Horizontal)
            # y la línea de operación hacia el plato superior (Diagonal/Vertical)
            
            for i in range(len(platos_list)):
                p_curr = platos_list[i]
                
                # 1. Línea Horizontal (Equilibrio en el plato)
                # Conecta x_curr (Líquido) con y_curr (Vapor) a T_curr
                ax.plot([p_curr['x'], p_curr['y']], [p_curr['T'], p_curr['T']], 
                        color='black', linestyle='--', linewidth=1, alpha=0.7)
                
                # 2. Línea hacia el siguiente plato (Operación)
                # Conecta el Vapor de este plato (y_curr, T_curr) 
                # con el Líquido del plato de arriba (x_next, T_next)
                if i < len(platos_list) - 1:
                    p_next = platos_list[i+1]
                    ax.plot([p_curr['y'], p_next['x']], [p_curr['T'], p_next['T']], 
                            color='gray', linestyle=':', linewidth=1)

        # Ajustes visuales
        ax.set_xlim(0, 1)
        ax.set_ylim(min(Tb_A, Tb_B) - 2, max(Tb_A, Tb_B) + 2)
        ax.set_xlabel(f"Composición x, y ({A_p.get('name', 'A')})")
        ax.set_ylabel("Temperatura (°C)")
        ax.set_title("Diagrama T-xy")
        ax.grid(True, linestyle=":", alpha=0.5)
        
        # Leyenda ubicada para no tapar (Arriba izquierda suele estar libre en benceno/tolueno)
        ax.legend(loc='upper left', fontsize='small', framealpha=0.8)
        
        # Guardar imagen
        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches='tight')
        plt.close(fig)
        return base64.b64encode(buf.getvalue()).decode("utf-8")


    def recalcular_sistema(e=None):
        """Función Principal: Recalcula todo el estado."""
        try:
            # Leer inputs
            Tb_A = float(txt_tb_a.value)
            Tb_B = float(txt_tb_b.value)
            P_ref_A = float(txt_p_ref_a.value)
            P_ref_B = float(txt_p_ref_b.value)
            
            if Tb_A >= Tb_B:
                 raise ValueError("Tb de A debe ser menor que la de B.")
            
            AA, BA = get_antoine_params(Tb_A, P_ref_A)
            AB, BB = get_antoine_params(Tb_B, P_ref_B)

            # Guardar en el Objeto State
            state.A_params = {'name': txt_name_a.value, 'Tb': Tb_A, 'A': AA, 'B': BA}
            state.B_params = {'name': txt_name_b.value, 'Tb': Tb_B, 'A': AB, 'B': BB}
            
            # Si el evento viene del botón reiniciar (no de "Destilar"), leemos x0 del input
            # Si viene de "Destilar", usamos el x_pot que ya está en state
            if e is not None and e.control == btn_recalc:
                state.x_pot = float(txt_x0.value)
                state.moles_pot = 100.0
                state.step_count = 0
            
            # Validar
            if not (0 < state.x_pot < 1): raise ValueError("x_inicial debe ser entre 0 y 1")
            n_platos = int(slider_platos.value)

            # --- CALCULO DE PLATOS ---
            state.platos = [] # Limpiar lista anterior
            
            # 1. Balón (Reboiler)
            T_pot, y_pot = get_T_bub(state.x_pot, AA, BA, AB, BB)
            state.platos.append({'type': 'balon', 'T': T_pot, 'x': state.x_pot, 'y': y_pot})
            
            # 2. Platos
            current_y = y_pot
            for i in range(n_platos):
                x_plate = current_y # Asumimos reflujo total/ideal para la línea operativa simple
                T_plate, y_plate = get_T_bub(x_plate, AA, BA, AB, BB)
                state.platos.append({'type': 'plato', 'n': i+1, 'T': T_plate, 'x': x_plate, 'y': y_plate})
                current_y = y_plate

            # --- ACTUALIZAR UI ---
            # Pureza
            x_destilado = state.platos[-1]['y']
            purity_color = Colors.GREEN_700 if x_destilado > 0.95 else Colors.RED_700
            lbl_info_top.value = f"{x_destilado*100:.1f} %"
            lbl_info_top.color = purity_color
            
            # Lista de Resultados
            col_data_display.controls.clear()
            lbl_moles.value = f"Moles Balón: {state.moles_pot:.1f} | Pasos: {state.step_count}"

            # Mostrar lista invertida (Tope arriba)
            for i, p in enumerate(reversed(state.platos)):
                is_balon = (p['type'] == 'balon')
                level_txt = "BALÓN" if is_balon else f"Plato {len(state.platos) - i - 1}"
                
                # Color de fondo según concentración
                x_val = p['x']
                if x_val > 0.8: bg = Colors.RED_100
                elif x_val < 0.2: bg = Colors.BLUE_100
                else: bg = Colors.WHITE
                
                card = ft.Container(
                    ft.Row([
                        ft.Text(level_txt, weight=ft.FontWeight.BOLD, width=60),
                        ft.Text(f"x={p['x']:.3f}", width=60),
                        ft.Text(f"y={p['y']:.3f}", width=60),
                        ft.Text(f"T={p['T']:.1f}°", width=60),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=5, margin=1, bgcolor=bg, border=ft.border.all(1, Colors.GREY_300)
                )
                col_data_display.controls.append(card)

            # Gráfico
            img_plot.src_base64 = dibujar_grafico_matplotlib()
            
            lbl_estado.value = f"Simulación OK. x_balón: {state.x_pot:.3f}"
            lbl_estado.color = Colors.BLUE_700

        except Exception as err:
            lbl_estado.value = f"Error: {err}"
            lbl_estado.color = Colors.RED
            state.platos = [] # Invalidar estado
            img_plot.src_base64 = None
            print(f"Error interno: {err}")
            
        page.update()


    def paso_destilacion(e):
        """Retira destilado y recalcula."""
        # Verificación directa sobre la lista del objeto state
        if not state.platos:
             lbl_estado.value = "⚠️ Error: Ejecute 'Iniciar' primero."
             page.update()
             return

        if state.moles_pot < 10:
            lbl_estado.value = "⚠️ Balón casi vacío. Deteniendo."
            page.update()
            return

        # Masa retirada
        delta_D = 5.0
        x_D = state.platos[-1]['y'] # Composición del vapor del tope
        
        moles_A = state.x_pot * state.moles_pot
        moles_A_new = moles_A - (x_D * delta_D)
        moles_total_new = state.moles_pot - delta_D
        
        # Actualizar estado
        state.moles_pot = moles_total_new
        state.x_pot = max(0.001, moles_A_new / moles_total_new)
        state.step_count += 1
        
        # Llamar a recalcular (sin evento, para mantener x_pot actual)
        recalcular_sistema(None)


    # --- LAYOUT DE LA PÁGINA ---
    btn_recalc = ft.ElevatedButton("🚀 Iniciar / Reiniciar", on_click=recalcular_sistema, 
                                   bgcolor=Colors.CYAN_300, color=Colors.BLACK)
    
    btn_step = ft.ElevatedButton("⬇ DESTILAR (Retirar 5 moles)", on_click=paso_destilacion, 
                                 bgcolor=Colors.GREEN_700, color=Colors.WHITE)

    page.add(
        ft.Text("⚗️ Simulador de Destilación Interactiva", size=24, weight=ft.FontWeight.BOLD),
        ft.Divider(),
        
        # Fila Superior: Configuración Componentes
        ft.Row([
            ft.Column([
                ft.Text("Componente A (Volátil)", color=Colors.RED_500, weight="bold"),
                txt_name_a, txt_tb_a, txt_p_ref_a
            ]),
            ft.VerticalDivider(),
            ft.Column([
                ft.Text("Componente B (Pesado)", color=Colors.BLUE_500, weight="bold"),
                txt_name_b, txt_tb_b, txt_p_ref_b
            ])
        ], alignment=ft.MainAxisAlignment.CENTER),
        
        ft.Divider(),
        
        # Fila Principal: Control y Gráficos
        ft.Row([
            # Columna Izquierda: Controles y Datos Numericos
            ft.Container(
                width=350,
                content=ft.Column([
                    ft.Text("Configuración Operativa", weight="bold"),
                    txt_x0,
                    slider_platos,
                    ft.Row([btn_recalc, btn_step], alignment=ft.MainAxisAlignment.CENTER),
                    ft.Divider(),
                    
                    ft.Text("Resultados de la Columna", weight="bold"),
                    ft.Container(
                        content=ft.Column([
                             ft.Text("Pureza Destilado:"),
                             lbl_info_top
                        ]),
                        padding=5, border=ft.border.all(1, Colors.GREY_400),
                        bgcolor=Colors.GREY_100
                    ),
                    lbl_moles,
                    ft.Divider(height=5),
                    # Lista con scroll de los platos
                    ft.Container(
                        content=col_data_display,
                        height=300,
                        border=ft.border.all(1, Colors.GREY_300),
                        padding=5
                    ),
                    lbl_estado
                ])
            ),
            
            ft.VerticalDivider(width=1),
            
            # Columna Derecha: Gráfico
            ft.Container(
                content=ft.Column([
                    ft.Text("Diagrama de Equilibrium (T-xy)", weight="bold"),
                    img_plot
                ], alignment=ft.MainAxisAlignment.CENTER)
            )
        ], alignment=ft.MainAxisAlignment.CENTER, vertical_alignment=ft.CrossAxisAlignment.START)
    )

    # Inicialización automática al cargar
    recalcular_sistema(e=ft.ControlEvent(target=btn_recalc, name="submit", data="", control=btn_recalc, page=page))

ft.app(target=main, view=ft.WEB_BROWSER, port=10000)
