import { HttpInterceptorFn } from '@angular/common/http';

/** Attach the session JWT to backend API calls. */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  if (req.url.startsWith('/api/')) {
    const token = localStorage.getItem('session_token');
    if (token && !req.headers.has('Authorization')) {
      req = req.clone({ setHeaders: { Authorization: `Bearer ${token}` } });
    }
  }
  return next(req);
};
