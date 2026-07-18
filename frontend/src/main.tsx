import React from 'react';import ReactDOM from 'react-dom/client';import {BrowserRouter} from 'react-router-dom';import {QueryClient,QueryClientProvider} from '@tanstack/react-query';import {Toaster} from 'sonner';import 'leaflet/dist/leaflet.css';import './index.css';import App from './App';
import {I18nProvider} from './lib/i18n';
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><I18nProvider><QueryClientProvider client={new QueryClient()}><BrowserRouter><App/><Toaster richColors position="top-right"/></BrowserRouter></QueryClientProvider></I18nProvider></React.StrictMode>)
if('serviceWorker' in navigator&&import.meta.env.PROD)navigator.serviceWorker.register('/sw.js').catch(()=>undefined);
