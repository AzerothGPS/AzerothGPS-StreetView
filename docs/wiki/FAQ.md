# FAQ

**The figure or the game button doesn't show on the map.**
StreetView needs a recent AzerothGPS. Update it, then restart the game.

**"Street View Pictures Missing" pops up.**
The pictures are a download of their own: install **AzerothGPS StreetView Data** from CurseForge (the note
shows its page), then restart the game completely. Already installed? It may be turned off: enable it in
the AddOns list at the character select screen.

**The street view is black, or says the picture is missing.**
Restart the game completely: new picture files only load on a full start, not on a `/reload`. `/sv probe`
checks that your client can show the pictures.

**Left and right are swapped when I drag.**
Type `/sv flipyaw`.

**My friend doesn't get the invitation.**
They need StreetView too, and you have to send the link yourself: it goes into your chat box, so press Enter.
For a whisper, target them and click **Target**. Games work on your realm and faction.

**Someone shows "guessed" but no points.**
That's on purpose. Points stay hidden until the round's result, so nobody can wait and copy the best
guess.

**The panel says someone is missing a map pack.**
They're on an older StreetView, and the game only uses street views everyone has. Updating fixes it.

**Will a /reload kick me out of a game?**
Nope. The game picks up where it was and catches up on what everyone else did meanwhile. Logging out
does end it, though.

**The box on the street view is covering what I want to see.**
Click the **-** in its corner. It shrinks down to just the timer, and **+** brings it back.

**Does StreetView play for me or move my character?**
No. It only shows pictures and the map. It never moves your character or presses keys for you.

**Does it work in dungeons?**
Yes, for the bosses. Open a dungeon's map in AzerothGPS and Shift-click a boss to see him in his room:
every dungeon and raid boss is in (see [[Coverage]]). It needs AzerothGPS 1.1.0 or later, and the top of the map says "Shift-click a boss: its street view" when it works. Dungeon spots
never come up in Where in the Azeroth?. `/sv here` can't find you inside a dungeon, because the game hides
your position there.

**Can I go inside buildings?**
Yes. Ironforge, Stormwind Keep and the Cathedral, the inns, Thunder Bluff's tents and Orgrimmar's halls are
all in, and they can come up in Where in the Azeroth? too.
