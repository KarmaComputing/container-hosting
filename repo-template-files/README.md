# Go forth and build! 🚀

By now, you have deployed a container, and in moments, you can visit your app
live!

> Be patient! In ~3 mins your app is live, at your [app url](APP_URL). It even has a free SSL/TLS certificate 🔒 you're welcome!

You probably want to add code to your app. Good news, your app is ready right now to start coding, which is simple:

1. Edit your code
2. Commit your code
3. Push your code `git push origin main`

Your app will be automatically re-deployed with the latest code at: APP_URL

> You app is deployed already and is working software. Gone are the days of spending weeks coding and then *another* week going to production. No. Go to production *early* and respond to change.

# How to code your app locally 💻 (on your laptop)

> Step 0: You need to download your repo to your computer:

```
git clone REPO_CLONE_URL
```

> See an error? You might need to setup permissions [here's a guide how to setup repo clone permissions](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account)

1. [Install docker](https://docs.docker.com/get-docker/)

2. Start your container locally: `docker-compose up`
3. Visit your app locally: http://127.0.0.1:5000/

## View your app locally

Visit: http://127.0.0.1:5000/

### Rebuild container (locally)
If you make changes to `Dockerfile`, then you need to rebuild your container image. To rebuild the container image:
```
docker-compose build
# or 
docker-compose up --build
```

# Which framework did you choose?

Need some help to get started?

- [**Ruby** quickstart guide](https://github.com/KarmaComputing/rails-quickstart)


## Questions

- How was this built? [All code is here](https://github.com/KarmaComputing/container-hosting)
