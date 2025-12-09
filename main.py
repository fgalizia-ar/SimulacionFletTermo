import flet as ft
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
