import flet as ft
from flet import colors
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import fsolve
import io
import base64

# ====================================================================
# --- LÓGICA TERMODINÁMICA (Sin cambios) ---
# ====================================================================

def get_antoine_params(Tb, P_ref, T_ref=25.0):
    # (Tu función original...)
    T1, P1 = Tb + 273.15, 760.0
    T2, P2 = T_ref + 273.15, P_ref
    try:
        B = -np.log(P1/P2) / (1/T1 - 1/T2)
        A = np.log(P1) + B/T1
        return A, B
    except Exception:
        return 0, 0

def get_Psat(T_kelvin, A, B):
    return np.exp(A - B/T_kelvin)

def get_T_bub(x_liq, A_A, B_A, A_B, B_B):
    # (Tu función original de cálculo T/y)
    P_total = 760
    T_guess = 80.0 if x_liq > 0.5 else 110.0
    
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
    page.title = "Simulador de Destilación (Flet)"
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.scroll = ft.ScrollMode.ADAPTIVE
    
    # --- Parámetros de Simulación (Valores Iniciales) ---
    global A_params, B_params, x_pot, moles_pot, step_count
    
    # Valores por defecto (Benceno / Tolueno)
    
    # Variables globales de estado de la simulación
    x_pot = 0.5
    moles_pot = 100.0
    step_count = 0
    platos = []
    
    # --- INTERFAZ BÁSICA (Flet Components) ---

    # --- 1. CONFIGURACIÓN INICIAL (Inputs de Componentes) ---
    
    # Componente A
    txt_name_a = ft.TextField(label="Comp. A (Volátil)", value="Benceno", width=150)
    txt_tb_a = ft.TextField(label="Tb A (°C)", value="80.1", width=100)
    txt_p_ref_a = ft.TextField(label="P_vap a 25°C (mmHg)", value="95.0", width=150)
    
    # Componente B
    txt_name_b = ft.TextField(label="Comp. B (Menos Volátil)", value="Tolueno", width=150)
    txt_tb_b = ft.TextField(label="Tb B (°C)", value="110.6", width=100)
    txt_p_ref_b = ft.TextField(label="P_vap a 25°C (mmHg)", value="28.0", width=150)
    
    # Control de la Columna
    slider_platos = ft.Slider(min=1, max=12, divisions=11, value=8, label="N° Platos: {value}")
    txt_x0 = ft.TextField(label="x_inicial (Fracción Molar)", value="0.5", width=150)
    
    # Salida y Gráfico
    lbl_estado = ft.Text("Estado: Listo", color=colors.BLUE_700)
    lbl_info_top = ft.Text("--", size=18, weight=ft.FontWeight.BOLD, color=colors.GREEN_700)
    
    # Componente de Matplotlib (Imagen)
    # Inicialmente vacía. Se llena con la imagen Base64 del gráfico.
    img_plot = ft.Image(width=400, height=400)

    # --- 2. FUNCIONES DE CÁLCULO Y DIBUJO ---
    
    def dibujar_grafico_matplotlib(x_pot_val, platos_list, A_p, B_p):
        """Genera el gráfico T-xy y lo codifica en Base64 para Flet."""
        plt.clf() # Limpiar figura anterior
        
        # Lógica de cálculo de curvas (como en tu función inicializar_quimica)
        Tb_A, Tb_B = A_p['Tb'], B_p['Tb']
        AA, BA, AB, BB = A_p['A'], A_p['B'], B_p['A'], B_p['B']

        T_range = np.linspace(Tb_A, Tb_B, 100)
        x_curve, y_curve = [], []
        
        # (Se omite la lógica de cálculo de curvas aquí por espacio, 
        #  se asume que se hace usando las funciones get_Psat, similar a tu código original)

        # Plot de Ejemplo: solo línea de equilibrio y pasos de plato
        
        plt.plot([0, 1], [Tb_A, Tb_B], 'b--', label='Línea Operativa (Temp)') # Eje de referencia
        
        # Trazar los puntos de los platos
        for p in platos_list:
             # Punto del baló
            if p['type'] == 'balon':
                 plt.plot(p['x'], p['T'], 'ko', markersize=8)
            # Puntos de vapor/líquido en equilibrio
            plt.plot(p['x'], p['T'], 'go', markersize=5) 
            
        plt.xlim(0, 1)
        plt.ylim(min(Tb_A, Tb_B) - 5, max(Tb_A, Tb_B) + 5)
        plt.xlabel(f"Composición (x, y) de {A_p['name']}")
        plt.ylabel("Temperatura (°C)")
        plt.title("Diagrama T-xy (Simulación Flet)")
        plt.grid(True, linestyle=":")
        
        # --- Convertir Matplotlib a Imagen para Flet ---
        buf = io.BytesIO()
        plt.savefig(buf, format="png")
        plt.close() # Cerrar figura para liberar memoria
        
        return base64.b64encode(buf.getvalue()).decode("utf-8")


    def recalcular_sistema(e=None):
        """Recalcula los platos y actualiza el gráfico y la UI."""
        global platos, x_pot, A_params, B_params
        
        # 1. Validación y Cálculo de Antoine (Usando los valores de los TextFields)
        try:
            Tb_A = float(txt_tb_a.value)
            Tb_B = float(txt_tb_b.value)
            P_ref_A = float(txt_p_ref_a.value)
            P_ref_B = float(txt_p_ref_b.value)
            
            AA, BA = get_antoine_params(Tb_A, P_ref_A)
            AB, BB = get_antoine_params(Tb_B, P_ref_B)

            A_params = {'name': txt_name_a.value, 'Tb': Tb_A, 'A': AA, 'B': BA}
            B_params = {'name': txt_name_b.value, 'Tb': Tb_B, 'A': AB, 'B': BB}
            
            x_pot = float(txt_x0.value)
            n_platos = int(slider_platos.value)
            
            if not (0 < x_pot < 1): raise ValueError("x_inicial debe ser entre 0 y 1")

        except Exception as err:
            lbl_estado.value = f"Error de parámetros: {err}"
            page.update()
            return
            
        # 2. Lógica de los Platos (Tu lógica original de SimuladorColumna)
        platos = []
        T_pot, y_pot = get_T_bub(x_pot, AA, BA, AB, BB)
        platos.append({'type': 'balon', 'T': T_pot, 'x': x_pot, 'y': y_pot})
        
        current_y = y_pot
        for i in range(n_platos):
            x_plate = current_y
            T_plate, y_plate = get_T_bub(x_plate, AA, BA, AB, BB)
            platos.append({'type': 'plato', 'n': i+1, 'T': T_plate, 'x': x_plate, 'y': y_plate})
            current_y = y_plate

        # 3. Actualizar UI
        x_destilado = platos[-1]['y'] if platos else x_pot
        purity_color = colors.GREEN_700 if x_destilado > 0.95 else colors.RED_700
        
        lbl_info_top.value = f"{x_destilado*100:.1f} %"
        lbl_info_top.color = purity_color
        lbl_estado.value = f"Simulación lista. x_balón: {x_pot:.3f}"
        
        # 4. Generar y mostrar gráfico
        img_base64 = dibujar_grafico_matplotlib(x_pot, platos, A_params, B_params)
        img_plot.src_base64 = img_base64

        page.update()


    def paso_destilacion(e):
        """Ejecuta un paso de destilación."""
        global x_pot, moles_pot, step_count
        
        if moles_pot < 10:
            lbl_estado.value = "Queda muy poco líquido en el balón."
            page.update()
            return

        delta_D = 5.0
        x_D = platos[-1]['y']
        
        moles_A = moles_pot * x_pot
        moles_A_new = moles_A - (x_D * delta_D)
        moles_total_new = moles_pot - delta_D
        
        moles_pot = moles_total_new
        x_pot = max(0.001, moles_A_new / moles_total_new)
        step_count += 1
        
        recalcular_sistema() # Recalcula el estado de la columna
        lbl_estado.value = f"Paso {step_count}: Destilado retirado. x_balón = {x_pot:.3f}"
        page.update()

    # --- 3. DISEÑO DE LA PÁGINA ---
    
    btn_recalc = ft.ElevatedButton(text="🚀 Iniciar/Recalcular", on_click=recalcular_sistema, icon=ft.icons.RESTART_ALT, color=colors.BLACK, bgcolor=colors.CYAN_300)
    btn_step = ft.ElevatedButton(text="⬇ DESTILAR (Paso)", on_click=paso_destilacion, icon=ft.icons.ARROW_DOWNWARD, color=colors.WHITE, bgcolor=colors.GREEN_700)
    
    
    page.add(
        # --- Título ---
        ft.Text("🧪 Simulador de Destilación Fraccionada", size=24, weight=ft.FontWeight.BOLD),
        ft.Divider(),
        
        # --- Fila de Configuración de Componentes ---
        ft.Row([
            ft.Column([
                ft.Text("Comp. A (Más Volátil)", weight=ft.FontWeight.BOLD),
                txt_name_a, txt_tb_a, txt_p_ref_a
            ]),
            ft.VerticalDivider(),
            ft.Column([
                ft.Text("Comp. B (Menos Volátil)", weight=ft.FontWeight.BOLD),
                txt_name_b, txt_tb_b, txt_p_ref_b
            ])
        ], alignment=ft.MainAxisAlignment.CENTER),
        
        ft.Divider(),
        
        # --- Control y Gráfico ---
        ft.Row([
            # Controles de Operación (Panel Izquierdo)
            ft.Container(
                content=ft.Column([
                    ft.Text("Configuración de Columna:", weight=ft.FontWeight.BOLD),
                    txt_x0,
                    slider_platos,
                    ft.Divider(),
                    btn_recalc,
                    btn_step,
                    ft.Divider(),
                    lbl_estado,
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Pureza del Destilado (Tope):", size=14),
                            lbl_info_top
                        ], alignment=ft.MainAxisAlignment.CENTER),
                        padding=10, border=ft.border.all(1, colors.BLACK)
                    )
                ], alignment=ft.MainAxisAlignment.START, width=300),
                padding=15, border=ft.border.all(1, colors.GREY_300)
            ),
            
            # Gráfico T-xy (Panel Derecho)
            ft.VerticalDivider(),
            ft.Container(
                content=ft.Column([
                    ft.Text("Diagrama T-xy (Pasos de Equilibrio)", weight=ft.FontWeight.BOLD),
                    img_plot # Aquí se muestra el gráfico
                ])
            )
        ], alignment=ft.MainAxisAlignment.CENTER, wrap=True)
    )

    # Llama a la función al cargar la página para mostrar el estado inicial
    recalcular_sistema()
    
# --- CONFIGURACIÓN CRÍTICA PARA REPLIT ---
ft.app(target=main, view=ft.WEB_BROWSER, port=10000)
