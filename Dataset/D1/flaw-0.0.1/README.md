# dpyselfembed
A way for selfbots to send embeds again.  
It uses [Rauf's embed generator](https://embed.rauf.wtf/).

### Install
> ```bash
> $ pip install dpyselfembed
> ```

### Example
> ```python
> import dpyselfembed
> 
> embed = dpyselfembed.Embed("dpyselfembed", 
>   description="A way for selfbots to send embeds again.", 
>   colour="ff0000"
> )
> embed.set_author("Benny")
> 
> url = embed.generate_url(hide_url=True) # You can also convert the embed to a string.
> print(url) # The url will be put in your ctx.send() content.
> ```

### Limitations
> Because the embeds are web embeds there are limitations.  
> - No footers.
> - Max 350 character description.

### Credits
> Used code from [Discord.py Self Embed](https://github.com/bentettmar/discord.py-self_embed)