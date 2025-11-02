# Deployment Guide - Railway

## Quick Deployment to Railway

### 1. Prerequisites
- GitHub account
- Railway account (sign up at [railway.app](https://railway.app))
- This repository pushed to GitHub

### 2. Deploy to Railway

#### Option A: One-Click Deploy (Recommended)

1. Click on "Deploy on Railway" button (if available)
2. Select your repository
3. Railway will automatically detect the configuration

#### Option B: Manual Deployment

1. **Create New Project**
   - Go to [railway.app](https://railway.app)
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your repository

2. **Add PostgreSQL Database**
   - In your project, click "New"
   - Select "Database"
   - Choose "PostgreSQL"
   - Railway will automatically set `DATABASE_URL`

3. **Configure Environment Variables**
   
   Go to your project settings and add these variables:
   
   ```bash
   # Required
   SECRET_KEY=your-super-secret-key-change-this
   FLASK_ENV=production
   
   # Telegram (for contact form notifications)
   TELEGRAM_BOT_TOKEN=your_bot_token
   TELEGRAM_CHAT_ID=your_chat_id
   
   # hCaptcha (anti-spam protection)
   HCAPTCHA_SITE_KEY=your_site_key
   HCAPTCHA_SECRET_KEY=your_secret_key
   
   # Optional - Email fallback
   MAIL_SERVER=smtp.example.com
   MAIL_PORT=587
   MAIL_USE_TLS=true
   MAIL_USERNAME=your_email
   MAIL_PASSWORD=your_password
   FALLBACK_EMAIL=contact@datasec.fr
   
   # Optional - Redis for rate limiting
   # REDIS_URL will be provided if you add Redis
   ```

4. **Deploy**
   - Railway will automatically deploy your application
   - The URL will be provided once deployment is complete
   - Example: `https://your-app.railway.app`

### 3. Configure Telegram Bot (Optional but Recommended)

1. **Create a Telegram Bot**
   - Open Telegram and search for @BotFather
   - Send `/newbot` and follow instructions
   - Copy the bot token

2. **Get Chat ID**
   - Send a message to your bot
   - Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Find your `chat_id` in the response

3. **Add to Railway**
   - Add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` as environment variables

### 4. Configure hCaptcha

1. **Sign up for hCaptcha**
   - Go to [hcaptcha.com](https://www.hcaptcha.com/)
   - Create an account
   - Add a new site
   - Copy the site key and secret key

2. **Add to Railway**
   - Add `HCAPTCHA_SITE_KEY` and `HCAPTCHA_SECRET_KEY` as environment variables

### 5. Custom Domain (Optional)

1. In Railway project settings, go to "Domains"
2. Click "Add Domain"
3. Follow instructions to configure DNS
4. SSL certificate will be automatically provisioned

### 6. Monitoring

Railway provides:
- Real-time logs
- Metrics dashboard
- Resource usage monitoring

Access them from your project dashboard.

### 7. Database Migrations

Migrations run automatically on deployment. If you need to run them manually:

```bash
# From Railway's terminal
flask db upgrade
```

### 8. Scaling

Railway automatically scales based on usage. You can also:
- Add more resources in project settings
- Configure auto-scaling rules
- Add Redis for better caching and rate limiting

### 9. Troubleshooting

**Application won't start:**
- Check logs in Railway dashboard
- Verify all required environment variables are set
- Ensure `DATABASE_URL` is configured (add PostgreSQL if missing)

**Contact form not working:**
- Verify Telegram bot token and chat ID
- Check that bot is not blocked
- Verify hCaptcha keys are correct

**Database errors:**
- Ensure PostgreSQL is added to project
- Check `DATABASE_URL` environment variable
- Run migrations: `flask db upgrade`

### 10. Cost Estimation

Railway pricing (as of 2024):
- **Hobby Plan**: $5/month
  - Includes reasonable resources for MVP
  - Good for testing and small traffic
  
- **Pro Plan**: Usage-based
  - Pay for what you use
  - Better for production with traffic

For MVP, Hobby plan is sufficient.

### 11. Backup Strategy

1. **Database Backups**
   - Railway provides automatic PostgreSQL backups
   - Can restore from dashboard

2. **Code Backups**
   - Your code is in GitHub
   - Railway deploys from GitHub

### 12. Monitoring & Alerts

Set up monitoring:
1. Use Railway's built-in monitoring
2. Add external monitoring (optional):
   - Uptime Robot
   - Pingdom
   - New Relic

### 13. Security Checklist

Before going live:
- [ ] Change `SECRET_KEY` to a strong random value
- [ ] Set `FLASK_ENV=production`
- [ ] Configure hCaptcha
- [ ] Set up Telegram notifications
- [ ] Review all environment variables
- [ ] Test contact form
- [ ] Verify HTTPS is working
- [ ] Check security headers (use securityheaders.com)
- [ ] Review logs for errors

## Next Steps After Deployment

1. **Test Everything**
   - Visit all pages
   - Submit contact form
   - Check Telegram notifications
   - Verify error pages

2. **SEO Setup**
   - Submit sitemap to Google Search Console
   - Verify ownership
   - Monitor indexing

3. **Performance**
   - Test with GTmetrix or PageSpeed Insights
   - Optimize images if needed
   - Configure CDN if needed

4. **Monitoring**
   - Set up uptime monitoring
   - Configure alerts
   - Review logs regularly

## Migration to VPS Later

When ready to migrate to a VPS:
1. Follow the VPS deployment guide in README.md
2. Export database from Railway
3. Import to your VPS PostgreSQL
4. Update DNS to point to VPS
5. Monitor for issues

## Support

For issues:
- Check Railway documentation
- Review application logs
- Contact support if needed

Railway support: https://railway.app/help
