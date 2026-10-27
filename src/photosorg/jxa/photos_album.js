// photosorg bridge to Photos.app, JavaScript for Automation.
//
// Album membership and keywords only. Nothing here edits, exports or deletes a photo.
//
// Usage:
//   osascript -l JavaScript photos_album.js ensure    <folder> <album>
//   osascript -l JavaScript photos_album.js add       <folder> <album> <uuid> [uuid ...]
//   osascript -l JavaScript photos_album.js remove    <folder> <album> <uuid> [uuid ...]
//   osascript -l JavaScript photos_album.js delete    <folder> <album>
//   osascript -l JavaScript photos_album.js kw-add    <keyword> <uuid> [uuid ...]
//   osascript -l JavaScript photos_album.js kw-remove <keyword> <uuid> [uuid ...]

'use strict';

function run(argv) {
  const action = argv[0];
  const Photos = Application('Photos');

  switch (action) {
    case 'ensure':
      return ensureAlbum(Photos, argv[1], argv[2]).created ? 'created' : 'exists';
    case 'add': {
      const album = ensureAlbum(Photos, argv[1], argv[2]).album;
      const found = [];
      const missing = [];
      argv.slice(3).forEach(function (u) {
        const item = resolve(Photos, u);
        if (item === null) {
          missing.push(u);
        } else {
          found.push(item);
        }
      });
      if (found.length > 0) {
        Photos.add(found, { to: album });
      }
      return JSON.stringify({ added: found.length, missing: missing });
    }
    case 'remove':
      return removeFromAlbum(Photos, argv[1], argv[2], argv.slice(3));
    case 'delete': {
      const album = findAlbum(Photos, argv[1], argv[2]);
      if (album !== null) {
        Photos.delete(album); // deletes the album container only, never its photos
      }
      return 'deleted';
    }
    case 'kw-add':
      return setKeyword(Photos, argv[1], argv.slice(2), true);
    case 'kw-remove':
      return setKeyword(Photos, argv[1], argv.slice(2), false);
    default:
      throw new Error('unknown action: ' + action);
  }
}

// Photos media item ids look like "<uuid>/L0/001"; osxphotos reports the bare uuid.
function mediaItem(Photos, uuid) {
  return Photos.mediaItems.byId(uuid + '/L0/001');
}

// A photo osxphotos can see may still be out of reach for scripting (an iCloud Shared Library
// item, or one not synced yet). It is reported back instead of failing the whole batch.
function resolve(Photos, uuid) {
  const item = mediaItem(Photos, uuid);
  try {
    item.id();
    return item;
  } catch (e) {
    return null;
  }
}

function findFolder(Photos, name) {
  const matches = Photos.folders.whose({ name: name })();
  return matches.length > 0 ? matches[0] : null;
}

function findAlbum(Photos, folderName, albumName) {
  const folder = findFolder(Photos, folderName);
  if (folder === null) {
    return null;
  }
  const matches = folder.albums.whose({ name: albumName })();
  return matches.length > 0 ? matches[0] : null;
}

function ensureAlbum(Photos, folderName, albumName) {
  const existing = findAlbum(Photos, folderName, albumName);
  if (existing !== null) {
    return { album: existing, created: false };
  }
  let folder = findFolder(Photos, folderName);
  if (folder === null) {
    folder = Photos.make({ new: 'folder', named: folderName });
  }
  const album = Photos.make({ new: 'album', named: albumName, at: folder });
  return { album: album, created: true };
}

// The Photos scripting dictionary has no "remove from album" command. The album is rebuilt
// in place: a new album with the same name and the remaining items, then the old one is
// deleted. Photos themselves are untouched; only membership changes.
function removeFromAlbum(Photos, folderName, albumName, uuids) {
  const album = findAlbum(Photos, folderName, albumName);
  if (album === null) {
    return 'missing';
  }
  const drop = {};
  uuids.forEach(function (u) { drop[u] = true; });
  const keep = album.mediaItems.id().filter(function (id) { return !drop[id.split('/')[0]]; });
  const folder = findFolder(Photos, folderName);
  const fresh = Photos.make({ new: 'album', named: albumName + ' (rebuilding)', at: folder });
  if (keep.length > 0) {
    Photos.add(keep.map(function (id) { return Photos.mediaItems.byId(id); }), { to: fresh });
  }
  Photos.delete(album);
  fresh.name = albumName;
  return String(keep.length);
}

function setKeyword(Photos, keyword, uuids, present) {
  uuids.forEach(function (u) {
    const item = mediaItem(Photos, u);
    const current = item.keywords() || [];
    const without = current.filter(function (k) { return k !== keyword; });
    item.keywords = present ? without.concat([keyword]) : without;
  });
  return String(uuids.length);
}
