const { Euler, Matrix4, Vector3 } = require('three');

// Marker local position
const markerLocal = new Vector3(0, 0, 2.1);
const mX = new Matrix4().makeRotationX(0.508);
const mY = new Matrix4().makeRotationY(2.965);
const mMarker = new Matrix4().multiplyMatrices(mX, mY);
markerLocal.applyMatrix4(mMarker);
console.log("Marker world position on unrotated earth:", markerLocal);

// Earth rotation with XYZ order
const eulerXYZ = new Euler(-0.508, -2.965, 0, 'XYZ');
const earthXYZ = new Matrix4().makeRotationFromEuler(eulerXYZ);
const markerXYZ = markerLocal.clone().applyMatrix4(earthXYZ);
console.log("Marker final position with XYZ earth:", markerXYZ);

// Earth rotation with YXZ order
const eulerYXZ = new Euler(-0.508, -2.965, 0, 'YXZ');
const earthYXZ = new Matrix4().makeRotationFromEuler(eulerYXZ);
const markerYXZ = markerLocal.clone().applyMatrix4(earthYXZ);
console.log("Marker final position with YXZ earth:", markerYXZ);
