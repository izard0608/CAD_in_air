# app.utils.MathUtils.py  数学相关的实用函数
import math
import numpy as np

def distance(p1, p2):
    return np.linalg.norm(np.array(p1) - np.array(p2))

def vector_angle(p1, p2):
    p1, p2 = np.array(p1), np.array(p2)
    cos_theta = np.clip(np.dot(p1, p2) / (np.linalg.norm(p1) * np.linalg.norm(p2)), -1.0, 1.0)
    return np.degrees(np.arccos(cos_theta))


def unit(v):
    v = np.asarray(v, dtype=float)
    n = np.linalg.norm(v)
    return v / n if n > 0 else v

def normal_vector(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    nP = np.cross(a, b)
    if np.linalg.norm(nP) < 1e-12:
        return [0.0, 0.0, 0.0]
    ua = unit(a)
    ub = unit(b)
    v  = ua - ub
    nQ = np.cross(nP, v)
    if np.linalg.norm(nQ) < 1e-12:
        return [0.0, 0.0, 0.0]
    return (nQ / np.linalg.norm(nQ)).tolist()

def point_to_plane(x, p0, n):
    n = np.asarray(n, dtype=float)
    x = np.asarray(x, dtype=float)
    p0 = np.asarray(p0, dtype=float)
    nn = float(np.dot(n, n))
    if nn < 1e-12:
        return x.tolist()
    t = float(np.dot(x - p0, n) / nn)
    return (x - t * n).tolist()

def mid(a, b):
    return [(a[i]+b[i])/2.0 for i in range(3)]

def is_valid_point(point):
    return point[0] != 0.0 or point[1] != 0.0 or point[2] != 0.0
