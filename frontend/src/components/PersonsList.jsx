import { useEffect, useState } from 'react';
import { listPersons, updateFlag, deletePerson } from '../api';

export default function PersonsList({ admin }){
  const [persons, setPersons] = useState([]);
  const load = async () => {
    if(!admin) return;
    const res = await listPersons(admin.username, admin.password);
    setPersons(res.data.persons);
  };
  useEffect(()=>{load();}, [admin]);

  const handleFlag = async (pid, newFlag) => {
    const fd = new FormData();
    fd.append('username', admin.username);
    fd.append('password', admin.password);
    fd.append('person_id', pid);
    fd.append('flag', newFlag);
    await updateFlag(fd);
    load();
  };
  const handleDelete = async (pid) => {
    if(!window.confirm('Delete person?')) return;
    const fd = new FormData();
    fd.append('username', admin.username);
    fd.append('password', admin.password);
    fd.append('person_id', pid);
    await deletePerson(fd);
    load();
  };
  const imgUrl = (p) => `${window.location.origin.replace(/3000/, '8000')}/admin/person_image/${p.person_id}?username=${encodeURIComponent(admin.username)}&password=${encodeURIComponent(admin.password)}`;
  return (
    <div>
      <h3>Persons</h3>
      <table border="1" cellPadding="4">
        <thead><tr><th>Img</th><th>ID</th><th>Name</th><th>Flag</th><th>Metadata</th><th>Actions</th></tr></thead>
        <tbody>
          {persons.map(p=> (
            <tr key={p.person_id}>
              <td>{p.image_path && <img src={imgUrl(p)} alt={p.person_id} style={{width:48}} />}</td>
              <td>{p.person_id}</td>
              <td>{p.name}</td>
              <td>{p.flag}</td>
              <td style={{maxWidth:180, whiteSpace:'pre-wrap', fontSize:12}}>{p.metadata || '-'}</td>
              <td>
                <button onClick={()=>handleFlag(p.person_id, p.flag==='whitelist'?'blacklist':'whitelist')}>Toggle Flag</button>
                <button onClick={()=>handleDelete(p.person_id)}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}