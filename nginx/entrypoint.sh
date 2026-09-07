#!/bin/sh
htpasswd -bnBC 10 "$AUTH_USER" "$AUTH_PASSWORD" > /etc/nginx/.htpasswd
exec nginx -g "daemon off;"