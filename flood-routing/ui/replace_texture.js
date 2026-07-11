const fs = require('fs');
const https = require('https');

https.get('https://em-content.zobj.net/source/apple/354/round-pushpin_1f4cd.png', (res) => {
  const chunks = [];
  res.on('data', (d) => chunks.push(d));
  res.on('end', () => {
    const buffer = Buffer.concat(chunks);
    const base64 = buffer.toString('base64');
    const dataUri = 'data:image/png;base64,' + base64;
    
    let content = fs.readFileSync('./src/components/Globe.tsx', 'utf8');
    const regex = /'data:image\/svg\+xml;base64,[^']+'/g;
    content = content.replace(regex, "'" + dataUri + "'");
    fs.writeFileSync('./src/components/Globe.tsx', content);
    console.log('Replaced texture!');
  });
});
