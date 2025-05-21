import { Routes, Route } from 'react-router'
import Login from './components/Login'
import Register from './components/Register'
import Page from './app/dashboard/dashboard'
import ProtectedRoute from './components/ProtectedRoute'
import axios from 'axios';

function App() {
  axios.get('/api')
  .then(function (response) {
    // handle success
    console.log(response);
  })
  .catch(function (error) {
    // handle error
    console.log(error);
  })
  .finally(function () {
    // always executed
  });

  return (
    <>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/" element={<ProtectedRoute><Page /></ProtectedRoute>} />
      </Routes>
    </>
  )
}

export default App
