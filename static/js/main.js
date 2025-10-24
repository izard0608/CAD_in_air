const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera( 75, window.innerWidth / window.innerHeight, 0.1, 1000 );

const renderer = new THREE.WebGLRenderer();
renderer.setSize( window.innerWidth, window.innerHeight );
renderer.setAnimationLoop( animate );
document.body.appendChild( renderer.domElement );

const geometry = new THREE.BoxGeometry( 1, 1, 1 );
const material = new THREE.MeshPhongMaterial( { color: 0x0080ff } );
const cube = new THREE.Mesh( geometry, material );
scene.add( cube );

const ambientLight = new THREE.AmbientLight(0xffffff, 0.5); // 环境光
scene.add(ambientLight);

const directionalLight = new THREE.DirectionalLight(0xffffff, 1); // 定向光
directionalLight.position.set(5, 5, 5);
scene.add(directionalLight);

camera.position.z = 5;

function animate() {

  cube.rotation.x += 0.01;
  cube.rotation.y += 0.01;

  renderer.render( scene, camera );

}
