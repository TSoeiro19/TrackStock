// Hooks partilhados pelas páginas
import { useEffect, useRef, useState } from 'react';

// Chama fn a cada `ms` milissegundos (e logo ao montar, se `immediate`)
export function useInterval(fn, ms, immediate = false) {
  const saved = useRef(fn);
  saved.current = fn;
  useEffect(() => {
    if (immediate) saved.current();
    const id = setInterval(() => saved.current(), ms);
    return () => clearInterval(id);
  }, [ms, immediate]);
}

// Tema claro/escuro do Windows (os gráficos leem as cores do tema quando são criados)
export function useDarkTheme() {
  const query = '(prefers-color-scheme: dark)';
  const [dark, setDark] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const onChange = () => setDark(mq.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);
  return dark;
}

// Preferências da interface guardadas no browser (chaves com o prefixo "inv.")
export function useStoredState(key, initial) {
  const [value, setValue] = useState(() => {
    try {
      const v = localStorage.getItem('inv.' + key);
      return v == null ? initial : JSON.parse(v);
    } catch { return initial; }
  });
  useEffect(() => {
    try { localStorage.setItem('inv.' + key, JSON.stringify(value)); } catch { /* sem armazenamento */ }
  }, [key, value]);
  return [value, setValue];
}
