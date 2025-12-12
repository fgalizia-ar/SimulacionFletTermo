import flet as ft
from flet import Colors, Icons 
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import fsolve
import io
import base64
import sys

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
    
    # --- Parámetros de Simulación (Valores Iniciales) ---
    global A_params, B_params, x_pot, moles_pot, step_count
    
    x_pot = 0.5
    moles_pot = 100.0
    step_count = 0
    platos = []
    A_params, B_params = {}, {}
    
    # --- INTERFAZ BÁSICA (Flet Components) ---

    # 1. CONFIGURACIÓN INICIAL (Inputs de Componentes)
    txt_name_a = ft.TextField(label="Comp. A (Volátil)", value="Benceno", width=150)
    txt_tb_a = ft.TextField(label="Tb A (°C)", value="80.1", width=100)
    txt_p_ref_a = ft.TextField(label="P_vap a 25°C (mmHg)", value="95.0", width=150)
    
    txt_name_b = ft.TextField(label="Comp. B (Menos Volátil)", value="Tolueno", width=150)
    txt_tb_b = ft.TextField(label="Tb B (°C)", value="110.6", width=100)
    txt_p_ref_b = ft.TextField(label="P_vap a 25°C (mmHg)", value="28.0", width=150)
    
    # Control de la Columna
    slider_platos = ft.Slider(min=1, max=12, divisions=11, value=8, label="N° Platos: {value}")
    txt_x0 = ft.TextField(label="x_inicial (Fracción Molar)", value="0.5", width=150)
    
    # Salida y Gráfico
    lbl_estado = ft.Text("Estado: Iniciando...", color=Colors.BLUE_700)
    lbl_info_top = ft.Text("--", size=18, weight=ft.FontWeight.BOLD, color=Colors.GREEN_700)
    lbl_moles = ft.Text(f"Moles Pot: {moles_pot:.1f}", size=14)
    
    col_data_display = ft.Column(scroll=ft.ScrollMode.AUTO, height=300) 
    
    # Componente de Matplotlib (Imagen)
    img_plot = ft.Image(width=400, height=400)

    # --- 2. FUNCIONES DE CÁLCULO Y DIBUJO ---
    
    def dibujar_grafico_matplotlib(x_pot_val, platos_list, A_p, B_p):
        """Genera el gráfico T-xy y lo codifica en Base64 para Flet."""
        plt.clf()
        plt.figure(figsize=(4, 4))
        
        Tb_A, Tb_B = A_p['Tb'], B_p['Tb']
        AA, BA, AB, BB = A_p['A'], A_p['B'], B_p['A'], B_p['B']
        
        # --- Lógica de cálculo de curvas ---
        x_curve, y_curve, T_plot_curve = [], [], []
        T_test = np.linspace(Tb_A, Tb_B, 100)

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

        # --- Trazado de Curvas ---
        plt.plot(x_curve, T_plot_curve, 'b-', label='Líq. (Burbuja)', alpha=0.6)
        plt.plot(y_curve, T_plot_curve, 'r-', label='Vap. (Rocío)', alpha=0.6)
        
        # Trazar los puntos de los platos y las escaleras
        if platos_list:
            x_points = [p['x'] for p in platos_list]
            T_points = [p['T'] for p in platos_list]
            y_points = [p['y'] for p in platos_list]
            
            # Puntos de Líquido y Vapor
            plt.plot(x_points, T_points, 'ko', markersize=4, label='Ptos Liq.') 
            plt.plot(y_points, T_points, 'g^', markersize=4, label='Ptos Vap.') 
            
            # Dibujar las "escaleras" (Etapas Teóricas)
            if len(platos_list) > 1:
                # El bucle empieza desde el plato (i+1) hasta el destilado
                for i in range(len(platos_list) - 1):
                    x_curr = platos_list[i]['x']
                    T_curr = platos_list[i]['T']
                    y_curr = platos_list[i]['y']
                    T_next = platos_list[i+1]['T']
                    x_next = platos_list[i+1]['x']

                    # Línea Horizontal (Equilibrio: x_curr -> y_curr)
                    # En la curva, x_liq y y_vap están a la misma T_curr
                    plt.plot([x_curr, y_curr], [T_curr, T_curr], 'k--', linewidth=0.8)
                    
                    # Línea Vertical (Línea de Operación: y_curr del plato i -> x_liq del plato i+1, a diferentes T)
                    # El vapor y_curr sube a la T_next del plato superior (i+1), donde se condensa a x_next
                    # Usamos y_curr como composición x del plato superior
                    plt.plot([y_curr, x_next], [T_curr, T_next], 'k:', linewidth=0.8)

                # Línea Horizontal final para el destilado (Tope de la columna)
                x_dest = platos_list[-1]['x']
                y_dest = platos_list[-1]['y']
                T_dest = platos_list[-1]['T']
                plt.plot([x_dest, y_dest], [T_dest, T_dest], 'k--', linewidth=0.8)

        # Ajustes de Ejes y Leyenda
        plt.xlim(0, 1)
        plt.ylim(min(Tb_A, Tb_B) - 5, max(Tb_A, Tb_B) + 5)
        plt.xlabel(f"Composición (x, y) de {A_p['name']}")
        plt.ylabel("Temperatura (°C)")
        plt.title("Diagrama T-xy")
        plt.grid(True, linestyle=":")
        plt.legend(loc='upper right', fontsize='small') # Leyenda cambiada de posición
        
        # --- Convertir Matplotlib a Imagen para Flet ---
        buf = io.BytesIO()
        plt.savefig(buf, format="png")
        plt.close()
        
        return base64.b64encode(buf.getvalue()).decode("utf-8")


    def recalcular_sistema(e=None):
        """Recalcula los platos y actualiza el gráfico y la UI."""
        global platos, x_pot, A_params, B_params, moles_pot
        
        try:
            # 1. Validación y Cálculo de Antoine
            Tb_A = float(txt_tb_a.value)
            Tb_B = float(txt_tb_b.value)
            P_ref_A = float(txt_p_ref_a.value)
            P_ref_B = float(txt_p_ref_b.value)
            
            if Tb_A >= Tb_B:
                 raise ValueError("Tb de A debe ser menor que la de B.")
            
            AA, BA = get_antoine_params(Tb_A, P_ref_A)
            AB, BB = get_antoine_params(Tb_B, P_ref_B)

            A_params = {'name': txt_name_a.value, 'Tb': Tb_A, 'A': AA, 'B': BA}
            B_params = {'name': txt_name_b.value, 'Tb': Tb_B, 'A': AB, 'B': BB}
            
            x_pot = float(txt_x0.value)
            n_platos = int(slider_platos.value)
            
            if not (0 < x_pot < 1): raise ValueError("x_inicial debe ser entre 0 y 1")

            # 2. Lógica de los Platos
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
            purity_color = Colors.GREEN_700 if x_destilado > 0.95 else Colors.RED_700
            
            lbl_info_top.value = f"{x_destilado*100:.1f} %"
            lbl_info_top.color = purity_color
            
            # Limpiar y rellenar la lista de platos
            col_data_display.controls.clear()
            lbl_moles.value = f"Moles Pot: {moles_pot:.1f}"

            # Recorrido inverso para mostrar el destilado arriba
            for i, p in enumerate(reversed(platos)):
                level = f"P. {len(platos) - i}" if p['type'] == 'plato' else "Balón"
                comp_x = f"x={p['x']:.3f}"
                comp_y = f"y={p['y']:.3f}"
                T_val = f"T={p['T']:.1f}°C"
                
                # Cálculo de color dinámico basado en concentración (x)
                # Escala de Amarillo (bajo x) a Rojo (alto x)
                # Limitamos el color a un rango visible para Flet (ej. escala de 200 a 700)
                x_norm = max(0.0, min(1.0, p['x']))
                # Usamos una interpolación simple para el color: Amarillo para bajo x, Rojo para alto x
                
                if x_norm > 0.9:
                    bg_color = Colors.RED_200
                elif x_norm < 0.2:
                    bg_color = Colors.YELLOW_200
                else:
                    bg_color = Colors.LIGHT_GREEN_50

                col_data_display.controls.append(
                    ft.Container(
                        ft.Text(f"{level}: {comp_x} / {comp_y} / {T_val}", size=12),
                        padding=5, margin=1,
                        bgcolor=bg_color,
                        border=ft.border.all(1, Colors.GREY_300)
                    )
                )

            # 4. Generar y mostrar gráfico
            img_base64 = dibujar_grafico_matplotlib(x_pot, platos, A_params, B_params)
            img_plot.src_base64 = img_base64
            
            lbl_estado.value = f"Simulación lista. x_balón: {x_pot:.3f} | Moles restantes: {moles_pot:.1f}"

        except ValueError as err:
            lbl_estado.value = f"Error de Datos: {err}"
            img_plot.src_base64 = None
            platos = [] # Limpiar platos si hay error de datos
        except Exception as err:
            lbl_estado.value = f"Error de Cálculo: {err}"
            print(f"ERROR: {err}")
            img_plot.src_base64 = None
            platos = [] # Limpiar platos si hay error de cálculo
            
        page.update()


    def paso_destilacion(e):
        """Ejecuta un paso de destilación."""
        global x_pot, moles_pot, step_count
        
        # Eliminamos la verificación inicial que fallaba.
        # Si la simulación no ha corrido, recalcular_sistema lo detectará por datos malos.
        # Si los platos están vacíos, es porque hubo un error, y recalcular_sistema()
        # intentará recuperarse o mostrará el error.
        
        # Verificación crítica de estado:
        if not platos:
             lbl_estado.value = "Primero debe presionar 'Iniciar/Recalcular' para comenzar la simulación."
             page.update()
             return

        if moles_pot < 10:
            lbl_estado.value = "Queda muy poco líquido en el balón (< 10 moles). Deteniendo destilación."
            page.update()
            return

        delta_D = 5.0
        # Usamos el y_vap del último plato (tope)
        x_D = platos[-1]['y'] 
        
        moles_A = x_pot * moles_pot
        moles_A_new = moles_A - (x_D * delta_D)
        moles_total_new = moles_pot - delta_D
        
        moles_pot = moles_total_new
        x_pot = max(0.001, moles_A_new / moles_total_new)
        step_count += 1
        
        recalcular_sistema()
        lbl_estado.value = f"Paso {step_count}: Destilado retirado. x_balón = {x_pot:.3f}"
        page.update()

    # --- 3. DISEÑO DE LA PÁGINA ---
    
    btn_recalc = ft.ElevatedButton(text="🚀 Iniciar/Recalcular", on_click=recalcular_sistema, icon=ft.Icons.RESTART_ALT, color=Colors.BLACK, bgcolor=Colors.CYAN_300) 
    btn_step = ft.ElevatedButton(text="⬇ DESTILAR (Paso)", on_click=paso_destilacion, icon=ft.Icons.ARROW_DOWNWARD, color=Colors.WHITE, bgcolor=Colors.GREEN_700) 
    
    
    page.add(
        ft.Text("🧪 Simulador de Destilación Fraccionada", size=24, weight=ft.FontWeight.BOLD),
        ft.Divider(),
        
        # Fila de Configuración de Componentes
        ft.Row([
            ft.Column([
                ft.Text("Comp. A (Más Volátil)", weight=ft.FontWeight.BOLD, color=Colors.GREEN_800),
                txt_name_a, txt_tb_a, txt_p_ref_a
            ], alignment=ft.MainAxisAlignment.START),
            ft.VerticalDivider(),
            ft.Column([
                ft.Text("Comp. B (Menos Volátil)", weight=ft.FontWeight.BOLD, color=Colors.RED_800),
                txt_name_b, txt_tb_b, txt_p_ref_b
            ], alignment=ft.MainAxisAlignment.START)
        ], alignment=ft.MainAxisAlignment.CENTER),
        
        ft.Divider(),
        
        # Control y Gráfico
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
                    
                    # Panel de Resultados y Listado de Platos
                    ft.Text("Resultados:", weight=ft.FontWeight.BOLD),
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Pureza del Destilado (Tope):", size=14),
                            lbl_info_top
                        ], alignment=ft.MainAxisAlignment.CENTER),
                        padding=10, border=ft.border.all(1, Colors.GREY_500)
                    ),
                    ft.Divider(height=5),
                    lbl_moles,
                    col_data_display, 
                    
                    lbl_estado,
                    
                ], alignment=ft.MainAxisAlignment.START, width=300),
                padding=15, border=ft.border.all(1, Colors.GREY_300)
            ),
            
            # Gráfico T-xy (Panel Derecho)
            ft.VerticalDivider(),
            ft.Container(
                content=ft.Column([
                    ft.Text("Diagrama T-xy", weight=ft.FontWeight.BOLD),
                    img_plot
                ])
            )
        ], alignment=ft.MainAxisAlignment.CENTER, wrap=True)
    )

    # Bloque try/except para capturar fallos de Matplotlib/Inicialización en Render
    try:
        recalcular_sistema()
    except Exception as e:
        lbl_estado.value = f"Error Crítico: Servidor activo, pero no se pudo calcular el estado inicial."
        print(f"ERROR FATAL DE ARRANQUE: {e}")
        page.update()
    
# --- CONFIGURACIÓN CRÍTICA PARA RENDER ---
ft.app(target=main, view=ft.WEB_BROWSER, port=10000)
