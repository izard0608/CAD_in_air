// three-scene.js
class ThreeScene {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.objects = new Map();
        this.isInitialized = false;
        
        // 绘图状态
        this.isDrawing = false;
        this.currentLine = null;
        this.startPoint = null;
        this.dynamicLine = null;
        
        // 动画相关
        this.animationId = null;
        this.frameCount = 0;
        this.lastFpsUpdate = 0;
        this.currentFps = 0;
        
        this.init();
    }
    
    init() {
        if (!this.container) {
            console.error('容器元素未找到:', this.containerId);
            return;
        }
        
        // 创建场景
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x1a1a2e);
        
        // 创建相机
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;
        
        this.camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
        this.camera.position.set(0, 5, 10);
        this.camera.lookAt(0, 0, 0);
        
        // 创建渲染器
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(width, height);
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        
        // 清空容器并添加画布
        this.container.innerHTML = '';
        this.container.appendChild(this.renderer.domElement);
        
        // 添加光源
        this.setupLights();
        
        // 添加参考网格
        this.setupGrid();
        
        // 开始动画循环
        this.animate();
        
        this.isInitialized = true;
        console.log('3D场景初始化完成');
    }
    
    setupLights() {
        // 环境光
        const ambientLight = new THREE.AmbientLight(0x404040, 0.6);
        this.scene.add(ambientLight);
        
        // 方向光
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(10, 10, 5);
        directionalLight.castShadow = true;
        this.scene.add(directionalLight);
    }
    
    setupGrid() {
        const gridHelper = new THREE.GridHelper(20, 20, 0x444444, 0x222222);
        this.scene.add(gridHelper);
        
        const axesHelper = new THREE.AxesHelper(5);
        this.scene.add(axesHelper);
    }

    /**
     * 1. 画点功能
     */
    createPoint(parameters = {}) {
        console.log('🎯 createPoint方法被调用，参数:', parameters);
        
        const {
            position = [0, 0, 0],
            color = 0xffff00,
            size = 0.1,
            name = `point_${Date.now()}`
        } = parameters;

        console.log('🎯 解析后参数:', {position, color, size, name});

        // 用小球体表示点
        const geometry = new THREE.SphereGeometry(size, 16, 16);
        const material = new THREE.MeshBasicMaterial({ color });
        const point = new THREE.Mesh(geometry, material);
        
        point.position.set(...position);
        point.name = name;
        
        this.scene.add(point);
        this.objects.set(name, point);
        
        console.log(`✅ 创建点成功: ${name} 位置: [${position}]`);
        console.log('✅ 场景对象数量:', this.scene.children.length);
        
        return point;
}

    /**
     * 2. 开始画线（创建起点）
     */
    startDrawingLine(parameters = {}) {
        if (this.isDrawing) {
            console.warn('已经在画线状态中');
            return null;
        }

        const { position = [0, 0, 0] } = parameters;
        
        // 创建起点（绿色）
        this.startPoint = this.createPoint({
            position: position,
            color: 0x00ff00,
            name: `start_point_${Date.now()}`
        });

        // 创建动态线条用于预览
        this.dynamicLine = this.createDynamicLine();
        
        this.isDrawing = true;
        
        console.log('开始画线，起点:', position);
        return this.startPoint;
    }

    /**
     * 3. 更新画线（实时预览）
     */
    updateDrawingLine(parameters = {}) {
        if (!this.isDrawing || !this.dynamicLine) {
            console.warn('不在画线状态中');
            return null;
        }

        const { position = [0, 0, 0] } = parameters;
        const endPoint = new THREE.Vector3(...position);

        // 更新动态线条：从起点到当前位置
        const points = [
            new THREE.Vector3().copy(this.startPoint.position),
            endPoint
        ];

        this.updateDynamicLine(this.dynamicLine, points);
        
        console.log('更新画线，当前位置:', position);
        return this.dynamicLine;
    }

    /**
     * 4. 完成画线
     */
    finishDrawingLine(parameters = {}) {
        if (!this.isDrawing) {
            console.warn('不在画线状态中');
            return null;
        }

        const { position = [0, 0, 0], color = 0xffffff } = parameters;
        const endPoint = new THREE.Vector3(...position);

        const EPS = 1e-4;
        const isZeroLength = this.startPoint && this.startPoint.position.distanceTo(endPoint) < EPS;

        if (isZeroLength) {
            // ✅ 线段长度≈0：把起点改成红色，不再创建新点，避免重叠闪烁
            if (this.startPoint.material && this.startPoint.material.color) {
                this.startPoint.material.color.set(0xff0000);
            }
            this.startPoint.name = `point_${Date.now()}`; // 可选：重命名成普通点
        } else {
            // 正常情况：创建红色终点
            this.createPoint({
                position: position,
                color: 0xff0000,
                name: `end_point_${Date.now()}`
            });

            // 创建最终线段
            this.createLine({
                points: [
                    this.startPoint.position.toArray(),
                    position
                ],
                color: color,
                name: `line_${Date.now()}`
            });
        }

        // 清理动态预览线
        if (this.dynamicLine) {
            this.scene.remove(this.dynamicLine);
            this.dynamicLine = null;
        }

        // 重置状态
        this.isDrawing = false;
        this.startPoint = null;

        console.log('完成画线');
        return true;
    }


    /**
     * 5. 取消画线
     */
    cancelDrawingLine() {
        if (!this.isDrawing) return;

        // 清理动态预览线
        if (this.dynamicLine) {
            this.scene.remove(this.dynamicLine);
            this.dynamicLine = null;
        }
        
        // 清理起点
        if (this.startPoint) {
            this.scene.remove(this.startPoint);
            this.objects.delete(this.startPoint.name);
            this.startPoint = null;
        }

        this.isDrawing = false;
        console.log('取消画线');
    }

    /**
     * 6. 创建动态线条（用于实时预览）
     */
    createDynamicLine(maxPoints = 2) {
        const geometry = new THREE.BufferGeometry();
        const positions = new Float32Array(maxPoints * 3);
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

        const material = new THREE.LineBasicMaterial({ 
            color: 0xffff00,  // 黄色预览线
            linewidth: 2
        });

        const line = new THREE.Line(geometry, material);
        line.name = `dynamic_line_${Date.now()}`;
        
        this.scene.add(line);
        return line;
    }

    /**
     * 7. 更新动态线条顶点
     */
    updateDynamicLine(line, points) {
        const positions = line.geometry.attributes.position.array;
        
        points.forEach((point, index) => {
            if (index * 3 + 2 < positions.length) {
                positions[index * 3] = point.x;
                positions[index * 3 + 1] = point.y;
                positions[index * 3 + 2] = point.z;
            }
        });
        
        line.geometry.attributes.position.needsUpdate = true;
        line.geometry.setDrawRange(0, points.length);
    }

    /**
     * 8. 创建静态线条
     */
    createLine(parameters = {}) {
        const {
            points = [],
            color = 0xffffff,
            name = `line_${Date.now()}`
        } = parameters;

        // 将数组转换为Three.js向量
        const threePoints = points.map(p => new THREE.Vector3(...p));
        const geometry = new THREE.BufferGeometry().setFromPoints(threePoints);
        const material = new THREE.LineBasicMaterial({ color });
        const line = new THREE.Line(geometry, material);
        
        line.name = name;
        this.scene.add(line);
        this.objects.set(name, line);
        
        return line;
    }

    /**
     * 9. 画长方形
     */
    // three-scene.js 里替换整个 createRectangle(...)
    createRectangle(parameters = {}) {
    const {
        normal = [0, 1, 0],     // 平面法向（后端给）
        corner1 = [0, 0, 0],    // 对角点1（后端给，必须严格使用）
        corner2 = [1, 0, 1],    // 对角点2（后端给，必须严格使用）
        color = 0x3498db,
        opacity = 0.7,
        name = `rectangle_${Date.now()}`
    } = parameters;

    // === 基础向量 ===
    const c1 = new THREE.Vector3().fromArray(corner1);
    const c2 = new THREE.Vector3().fromArray(corner2);
    const n  = new THREE.Vector3().fromArray(normal).normalize();

    const center = new THREE.Vector3().addVectors(c1, c2).multiplyScalar(0.5);
    const d = new THREE.Vector3().subVectors(c2, c1); // 对角向量
    const len = d.length();

    if (!isFinite(len) || len < 1e-6 || !isFinite(n.length()) || n.length() < 1e-6) {
        console.warn("createRectangle: degenerate input", { len, n: n.toArray() });
        return null;
    }

    const dHat = d.clone().normalize();

    // 在平面内找与 dHat 垂直的单位向量 pHat
    let pHat = new THREE.Vector3().crossVectors(n, dHat);
    const pLen = pHat.length();
    if (pLen < 1e-8) {
        // 退化保护：如果 n 与 d 平行（理论上不该发生），随便找个不共线向量
        pHat = Math.abs(n.y) < 0.9 ? new THREE.Vector3(0, 1, 0) : new THREE.Vector3(1, 0, 0);
        pHat.crossVectors(n, pHat).normalize();
    } else {
        pHat.normalize();
    }

    // 在平面内把边轴设置为“相对对角线 ±45°”
    // a = rotate(dHat, +45°), b = rotate(dHat, -45°)
    const cos45 = Math.SQRT1_2;  // 1/√2
    const sin45 = Math.SQRT1_2;
    const a = new THREE.Vector3().addVectors(
        dHat.clone().multiplyScalar(cos45),
        pHat.clone().multiplyScalar(sin45)
    ).normalize();
    const b = new THREE.Vector3().addVectors(
        dHat.clone().multiplyScalar(cos45),
        pHat.clone().multiplyScalar(-sin45)
    ).normalize();

    // 为了让对角点精确等于 c1/c2，需要：
    // center ± (w/2 * a + h/2 * b) = center ± d/2
    // 选 θ=45° 且 w=h，可得 w = h = |d|/√2
    const w = len / Math.SQRT2;
    const h = len / Math.SQRT2;

    const ha = a.clone().multiplyScalar(w * 0.5);
    const hb = b.clone().multiplyScalar(h * 0.5);

    // 四个顶点（确保 c1/c2 精确为对角点）
    // v2 = center + ha + hb  应该等于 c2
    // v0 = center - ha - hb  应该等于 c1
    const v0 = center.clone().sub(ha).sub(hb); // 应等于 c1
    const v1 = center.clone().sub(ha).add(hb);
    const v2 = center.clone().add(ha).add(hb); // 应等于 c2
    const v3 = center.clone().add(ha).sub(hb);

    // 用自定义四边形（两个三角形）来建几何，避免 PlaneGeometry 的角落不对齐
    const geo = new THREE.BufferGeometry();
    const positions = new Float32Array([
        v0.x, v0.y, v0.z,
        v1.x, v1.y, v1.z,
        v2.x, v2.y, v2.z,
        v3.x, v3.y, v3.z
    ]);
    const indices = new Uint16Array([
        0, 1, 2,  // 三角1
        0, 2, 3   // 三角2
    ]);

    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setIndex(new THREE.BufferAttribute(indices, 1));
    geo.computeVertexNormals(); // 直接用拓扑法线；如要强行用 n，可覆写法线属性

    const mat = new THREE.MeshStandardMaterial({
        color,
        transparent: true,
        opacity,
        side: THREE.DoubleSide
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.name = name;

    this.scene.add(mesh);
    this.objects.set(name, mesh);

    // 边框（更直观）
    const edgesGeo = new THREE.EdgesGeometry(geo);
    const edgesMat = new THREE.LineBasicMaterial({ color: 0xff0000 });
    const edgeLines = new THREE.LineSegments(edgesGeo, edgesMat);
    edgeLines.name = `${name}_edges`;
    this.scene.add(edgeLines);
    this.objects.set(edgeLines.name, edgeLines);

    // 日志核验：c1/c2 是否被精确复原
    const v0err = v0.distanceTo(c1);
    const v2err = v2.distanceTo(c2);
    console.log(`✅ createRectangle ok: ${name}`, {
        center: center.toArray(),
        normal: n.toArray(),
        diag_len: len,
        v0_to_c1_error: v0err,
        v2_to_c2_error: v2err
    });

    return mesh;
    }


    // ==================== 基础功能 ====================

    createCube(parameters = {}) {
        const {
            size = 1,
            position = [0, 0, 0],
            color = 0x3498db,
            name = `cube_${Date.now()}`
        } = parameters;

        const geometry = new THREE.BoxGeometry(size, size, size);
        const material = new THREE.MeshBasicMaterial({ color });
        const cube = new THREE.Mesh(geometry, material);
        
        cube.position.set(...position);
        cube.name = name;
        
        this.scene.add(cube);
        this.objects.set(name, cube);
        
        return cube;
    }
    
    createSphere(parameters = {}) {
        const {
            radius = 0.5,
            position = [0, 0, 0],
            color = 0xe74c3c,
            name = `sphere_${Date.now()}`
        } = parameters;

        const geometry = new THREE.SphereGeometry(radius, 32, 32);
        const material = new THREE.MeshBasicMaterial({ color });
        const sphere = new THREE.Mesh(geometry, material);
        
        sphere.position.set(...position);
        sphere.name = name;
        
        this.scene.add(sphere);
        this.objects.set(name, sphere);
        
        return sphere;
    }

    // 物体操作
    selectObject(objectName) {
        this.objects.forEach(obj => {
            if (obj.userData && obj.userData.isSelected) {
                if (obj.material && 'emissive' in obj.material) {
   obj.material.emissive.set(0x000000);
  }
                obj.userData.isSelected = false;
            }
        });
        
        const object = this.objects.get(objectName);
        if (object) {
            if (object.material && 'emissive' in object.material) {
    object.material.emissive.set(0x444444);
  }
            object.userData.isSelected = true;
            return object;
        }
        return null;
    }
    
    moveObject(objectName, newPosition) {
        const object = this.objects.get(objectName);
        if (object) {
            object.position.set(...newPosition);
            return true;
        }
        return false;
    }
    
    deleteObject(objectName) {
        const object = this.objects.get(objectName);
        if (object) {
            this.scene.remove(object);
            this.objects.delete(objectName);
            return true;
        }
        return false;
    }
    
    clearScene() {
        this.objects.forEach((object, name) => {
            this.scene.remove(object);
        });
        this.objects.clear();
        
        // 重置绘图状态
        this.cancelDrawingLine();
    }

    // 动画循环
    animate() {
        this.animationId = requestAnimationFrame(() => this.animate());
        
        // 更新FPS计数
        this.updateFPS();
        
        // 渲染场景
        this.renderer.render(this.scene, this.camera);
    }
    
    updateFPS() {
        this.frameCount++;
        const now = performance.now();
        
        if (now >= this.lastFpsUpdate + 1000) {
            this.currentFps = Math.round((this.frameCount * 1000) / (now - this.lastFpsUpdate));
            this.lastFpsUpdate = now;
            this.frameCount = 0;
            
            // 更新UI显示
            const fpsElement = document.getElementById('fps');
            if (fpsElement) {
                fpsElement.textContent = this.currentFps;
            }
        }
    }
    
    // 响应式调整
    onResize() {
        if (!this.isInitialized) return;
        
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;
        
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    }
    
    // 销毁
    destroy() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
        
        if (this.renderer) {
            this.renderer.dispose();
        }
        
        this.objects.clear();
        this.isInitialized = false;
    }
}