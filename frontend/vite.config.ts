import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins:[react()],
  build:{
    rollupOptions:{
      output:{
        manualChunks(id){
          if(!id.includes('node_modules'))return;
          if(id.includes('recharts')||id.includes('d3-'))return 'charts';
          if(id.includes('leaflet'))return 'maps';
          if(id.includes('framer-motion'))return 'motion';
          if(id.includes('@tanstack'))return 'query';
          if(id.includes('react-dom')||id.includes('react-router')||id.includes('/react/'))return 'react-vendor';
        }
      }
    }
  }
});
