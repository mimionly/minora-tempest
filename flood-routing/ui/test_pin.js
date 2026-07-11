const { CylinderGeometry, SphereGeometry } = require('three');

const needle = new CylinderGeometry(0.005, 0.005, 0.1, 8);
const headBase = new CylinderGeometry(0.03, 0.01, 0.06, 16);
const headTop = new SphereGeometry(0.03, 16, 16);

console.log("Needle bounds:", needle.boundingBox);
console.log("HeadBase bounds:", headBase.boundingBox);
console.log("HeadTop bounds:", headTop.boundingBox);
